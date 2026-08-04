import aiosqlite
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates

from app.database import DB_FILE, get_user_id
from app.core.security import require_auth
from app.models import MessageCreate

templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["Messages"])

@router.post("/messages/{target_username}")
async def send_message(target_username: str, message: MessageCreate, current_user: dict = Depends(require_auth)):
    """Saves a message only if the users have an accepted connection."""
    
    if not message.clean_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Message cannot be empty"
        )

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        my_id = await get_user_id(db, current_user["sub"])
        target_id = await get_user_id(db, target_username)

        if not target_id or not my_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )

        async with db.execute("""
            SELECT status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (my_id, target_id, target_id, my_id)) as cursor:
            connection = await cursor.fetchone()
            
        if not connection or connection["status"] != "accepted":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You can only message accepted connections."
            )

        await db.execute(
            "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
            (my_id, target_id, message.clean_content)
        )
        await db.commit()

    return {"message": "Message sent!"}


@router.get("/messages/{target_username}")
async def get_messages(target_username: str, current_user: dict = Depends(require_auth)):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        my_id = await get_user_id(db, current_user["sub"])
        target_id = await get_user_id(db, target_username)

        if not target_id or not my_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )

        async with db.execute("""
            SELECT status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (my_id, target_id, target_id, my_id)) as cursor:
            connection = await cursor.fetchone()

        if not connection or connection["status"] != "accepted":
            return {
                "messages": [],
                "status": "blocked",
                "detail": "You must accept the connection to view messages."
            }

        async with db.execute("""
            SELECT sender_id, content, timestamp
            FROM messages
            WHERE (sender_id = ? AND receiver_id = ?)
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp ASC
        """, (my_id, target_id, target_id, my_id)) as cursor:
            messages = await cursor.fetchall()

        formatted_messages = [
            {
                "sender": current_user["sub"] if msg["sender_id"] == my_id else target_username,
                "content": msg["content"],
                "timestamp": msg["timestamp"]
            }
            for msg in messages
        ]

    return {"messages": formatted_messages, "status": "connected"}