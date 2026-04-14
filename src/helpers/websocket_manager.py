from fastapi import WebSocket
from typing import Dict, List
from uuid import UUID
import logging

logger = logging.getLogger("uvicorn.error")

class ConnectionManager:
    def __init__(self):
        # This dictionary acts as our "phonebook". 
        # It maps a Conversation UUID to a list of active WebSocket connections.
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: UUID):
        """Accepts a new connection and adds it to the list for that conversation."""
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: UUID):
        """Removes a disconnected client from our phonebook."""
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
            # Clean up the memory if no one is watching this conversation anymore
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]

    async def broadcast_to_conversation(self, conversation_id: UUID, message: dict):
        """Sends a JSON message to all clients connected to a specific conversation."""
        if conversation_id in self.active_connections:
            for connection in self.active_connections[conversation_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    # Edge Case: If a connection died but hasn't been cleaned up yet, 
                    # we ignore the error so it doesn't crash the loop for other viewers.
                    logger.warning(f"Failed to send WS message: {e}")

manager = ConnectionManager()