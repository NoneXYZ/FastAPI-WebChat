from typing import Dict, List
from fastapi import WebSocket
import json

class ChatConnectionManager:
    def __init__(self):
        # Maps user_id -> list of active WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_private_message(self, message: dict, sender: int, receiver: int, current_ws: WebSocket | None = None):
        """Sends a message to both the sender and receiver if they are online."""
        payload = json.dumps(message)

        if receiver in self.active_connections:
            for connection in list(self.active_connections[receiver]):
                if connection is not current_ws:
                    await connection.send_text(payload)

        if sender in self.active_connections:
            for connection in list(self.active_connections[sender]):
                await connection.send_text(payload)
