import json
import inspect
import aiosqlite
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from app.models import MessageCreate
from app.core.security import COOKIE_NAME, decode_jwt, DB_FILE_NAME
from app.websockets.managers import ChatConnectionManager
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

manager = ChatConnectionManager()
router = APIRouter(prefix="/api", tags=["WebSockets"])
password_hash = PasswordHash((BcryptHasher(),))

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    token = websocket.cookies.get(COOKIE_NAME)
    user_payload = decode_jwt(token) if token else None
    
    if not user_payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    my_id = int(user_payload["id"])
    current_username = user_payload.get("sub") or user_payload.get("username")

    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM users WHERE id = ?", (my_id,)) as cursor:
            me = await cursor.fetchone()
        if not me:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(my_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
                target_id_raw = payload.get("receiver_id")
                try:
                    target_id = int(target_id_raw)
                except (TypeError, ValueError):
                    target_id = None
            except json.JSONDecodeError:
                continue

            if target_id is None:
                await websocket.send_json({"error": "Missing receiver_id"})
                continue
            
            try:
                message_data = MessageCreate(**payload)
            except ValidationError as e:
                await websocket.send_json({"error": "Validation failed", "details": e.errors()})
                continue
            
            async with aiosqlite.connect(DB_FILE_NAME) as db:
                db.row_factory = aiosqlite.Row
                
                async with db.execute("SELECT id FROM users WHERE id = ?", (target_id,)) as cursor:
                    target = await cursor.fetchone()
                if not target:
                    await websocket.send_json({"error": "User not found"})
                    continue
                
                async with db.execute("""
                    SELECT status FROM connections
                    WHERE (requester_id = ? AND receiver_id = ?)
                       OR (requester_id = ? AND receiver_id = ?)
                """, (my_id, target_id, target_id, my_id)) as cursor:
                    connection = await cursor.fetchone()
                
                if not connection or connection["status"] != "accepted":
                    await websocket.send_json({"error": "You are not friends with this user"})
                    continue
                
                await db.execute(
                    "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                    (my_id, target_id, message_data.clean_content)
                )
                await db.commit()
            
            message_out = {
                "sender_id": my_id,
                "receiver_id": target_id,
                "sender": current_username,
                "content": message_data.clean_content,
                "client_msg_id": message_data.client_msg_id
            }
            
            await manager.send_private_message(
                message=message_out, 
                sender=my_id, 
                receiver=target_id, 
                current_ws=websocket
            )
            
    except WebSocketDisconnect:
        pass
    finally:
        res = manager.disconnect(my_id, websocket)
        if inspect.isawaitable(res):
            await res
