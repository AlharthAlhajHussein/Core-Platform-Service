from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import Conversation, Message, UsageLog, Agent
from models.conversations import ConversationStatus
from models.messages import SenderType, MessageType
from helpers.websocket_manager import manager
from helpers.gcs_helper import generate_signed_url
from views.interaction_schemas import InteractionSyncSchema

class InteractionService:
    """
    Handles the high-volume synchronization of interactions from the AI-Orchestrator.
    This service is optimized for performance and data consistency.
    """

    async def sync_interaction(self, db: AsyncSession, payload: InteractionSyncSchema):
        """
        Atomically syncs a full user-AI interaction to the database.
        This involves:
        1. Upserting the Conversation record.
        2. Inserting the User and AI messages.
        3. Upserting the monthly UsageLog with incremented counters.
        """
        try:
            # Safely generate a preview even if the message has no text (e.g., a standalone image)
            ai_preview = payload.ai_response.text
            if not ai_preview:
                ai_preview = f"[{payload.ai_response.message_type.value.upper()}]"
            ai_preview = ai_preview[:100]

            # --- Step 1: Find or Create Conversation Session ---
            # Fetch the most recent conversation for this specific user & agent
            stmt = select(Conversation).filter(
                Conversation.agent_id == payload.agent_id,
                Conversation.sender_id == payload.sender_id
            ).order_by(Conversation.created_at.desc()).limit(1)
            
            result = await db.execute(stmt)
            conversation = result.scalar_one_or_none()

            if not conversation:
                # Create a brand new active conversation ticket
                conversation = Conversation(
                    agent_id=payload.agent_id,
                    company_id=payload.company_id,
                    sender_id=payload.sender_id,
                    platform=payload.platform,
                    last_message_preview=ai_preview,
                    last_activity_at=payload.ai_response.message_time,
                    status=ConversationStatus.ACTIVE
                )
                db.add(conversation)
                await db.flush() # Generates the UUID immediately
            else:
                # Append to the existing active/escalated conversation
                conversation.last_message_preview = ai_preview
                conversation.last_activity_at = payload.ai_response.message_time
                # Note: We intentionally do not change the status if it's PENDING_HUMAN,
                # so human agents don't lose track of the escalated ticket!
                
            conversation_id = conversation.id

            # --- Step 2: Batch Insert Messages ---
            # Create message records for both the user and the AI.
            messages_to_create = [
                Message(
                    conversation_id=conversation_id,
                    sender_type=SenderType.USER,
                    message_type=payload.user_message.message_type,
                    media_url=payload.user_message.media_url,
                    timestamp=payload.user_message.message_time,
                    text=payload.user_message.text
                ),
                Message(
                    conversation_id=conversation_id,
                    sender_type=SenderType.AI,
                    message_type=payload.ai_response.message_type,
                    media_url=payload.ai_response.media_url,
                    timestamp=payload.ai_response.message_time,
                    text=payload.ai_response.text
                )
            ]
            db.add_all(messages_to_create)

            # --- Step 3: Upsert Usage Log (Atomic Increment) ---
            # This is the most critical part for preventing race conditions in billing.
            billing_month = datetime.now(timezone.utc).strftime('%Y-%m')

            # Fetch with row-level lock (FOR UPDATE) to safely prevent race conditions
            usage_stmt = select(UsageLog).with_for_update().filter(
                UsageLog.agent_id == payload.agent_id,
                UsageLog.billing_month == billing_month
            )
            usage_result = await db.execute(usage_stmt)
            usage_log = usage_result.scalar_one_or_none()

            if usage_log:
                usage_log.messages_sent += 1
                usage_log.tokens_used += payload.tokens_used
            else:
                new_usage_log = UsageLog(
                    company_id=payload.company_id,
                    agent_id=payload.agent_id,
                    billing_month=billing_month,
                    messages_sent=1,
                    tokens_used=payload.tokens_used
                )
                db.add(new_usage_log)

            # --- Step 4: Commit the entire transaction ---
            # If any of the above steps fail, the session will raise an exception
            # and the default behavior of the `async with` block for the session
            # will be to roll back everything.
            await db.commit()

            # --- Step 5: Broadcast to Connected Dashboards (WebSockets) ---
            # We format the payload identically to how the REST API returns messages
            user_msg_payload = {
                "id": str(messages_to_create[0].id),
                "sender_type": messages_to_create[0].sender_type.value,
                "text": messages_to_create[0].text,
                "media_url": generate_signed_url(messages_to_create[0].media_url),
                "timestamp": messages_to_create[0].timestamp.isoformat() if messages_to_create[0].timestamp else None
            }
            ai_msg_payload = {
                "id": str(messages_to_create[1].id),
                "sender_type": messages_to_create[1].sender_type.value,
                "text": messages_to_create[1].text,
                "media_url": generate_signed_url(messages_to_create[1].media_url),
                "timestamp": messages_to_create[1].timestamp.isoformat() if messages_to_create[1].timestamp else None
            }
            
            # Send both messages silently to anyone currently viewing this conversation thread!
            await manager.broadcast_to_conversation(conversation_id, {"type": "new_message", "message": user_msg_payload})
            await manager.broadcast_to_conversation(conversation_id, {"type": "new_message", "message": ai_msg_payload})

        except Exception as e:
            # In case of any error, the transaction is automatically rolled back.
            # We re-raise the exception to be handled by the calling router,
            # which will result in a 500 error response to the Orchestrator.
            # This signals that the sync failed and should be retried.
            await db.rollback()
            # Optionally log the error `e` here
            raise


interaction_service = InteractionService()