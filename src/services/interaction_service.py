from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import Conversation, Message, UsageLog, Agent
from models.messages import SenderType, MessageType
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

            # --- Step 1: Upsert Conversation ---
            # Find or create the conversation thread.
            conversation_stmt = pg_insert(Conversation).values(
                agent_id=payload.agent_id,
                company_id=payload.company_id,
                sender_id=payload.sender_id,
                platform=payload.platform,
                last_message_preview=ai_preview,
                last_activity_at=datetime.now(timezone.utc)
            ).on_conflict_do_update(
                # If a conversation with this agent_id and sender_id already exists...
                index_elements=['agent_id', 'sender_id'],
                # ...update these fields.
                set_={
                    'last_message_preview': ai_preview,
                    'last_activity_at': datetime.now(timezone.utc)
                }
            ).returning(Conversation.id)

            conversation_result = await db.execute(conversation_stmt)
            conversation_id = conversation_result.scalar_one()

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

            usage_log_stmt = pg_insert(UsageLog).values(
                company_id=payload.company_id,
                agent_id=payload.agent_id,
                billing_month=billing_month,
                messages_sent=1,
                tokens_used=payload.tokens_used
            ).on_conflict_do_update(
                # If a log for this agent and month already exists...
                index_elements=['agent_id', 'billing_month'],
                # ...atomically increment the counters.
                set_={
                    'messages_sent': UsageLog.messages_sent + 1,
                    'tokens_used': UsageLog.tokens_used + payload.tokens_used
                }
            )
            await db.execute(usage_log_stmt)

            # --- Step 4: Commit the entire transaction ---
            # If any of the above steps fail, the session will raise an exception
            # and the default behavior of the `async with` block for the session
            # will be to roll back everything.
            await db.commit()

        except Exception as e:
            # In case of any error, the transaction is automatically rolled back.
            # We re-raise the exception to be handled by the calling router,
            # which will result in a 500 error response to the Orchestrator.
            # This signals that the sync failed and should be retried.
            await db.rollback()
            # Optionally log the error `e` here
            raise


interaction_service = InteractionService()