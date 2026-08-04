import aiosqlite
from fastapi import APIRouter, HTTPException, Depends
from fastapi.templating import Jinja2Templates

from app.core.security import DB_FILE_NAME
from app.core.security import require_auth

templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["Connections"])

@router.get("/connections/status/{target_username}")
async def get_connection_status(target_username: str, current_user: dict = Depends(require_auth)):
    """Helper to tell the frontend exactly what relationship the two users have."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("SELECT id FROM users WHERE username = ?", (target_username,)) as cursor:
            target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if me["id"] == target["id"]:
            return {"status": "self"}

        async with db.execute("""
            SELECT requester_id, status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"])) as cursor:
            conn = await cursor.fetchone()

        if not conn:
            return {"status": "none"}
        if conn["status"] == "accepted":
            return {"status": "accepted"}
        if conn["requester_id"] == me["id"]:
            return {"status": "pending_outgoing"}

        return {"status": "pending_incoming"}


@router.post("/connections/{target_username}")
async def send_connection_request(target_username: str, current_user: dict = Depends(require_auth)):
    """Send a connection request. Auto-accepts if they already sent one to you."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("SELECT id FROM users WHERE username = ?", (target_username,)) as cursor:
            target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if me["id"] == target["id"]:
            raise HTTPException(status_code=400, detail="You cannot connect with yourself")

        async with db.execute("""
            SELECT id, requester_id, status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"])) as cursor:
            existing = await cursor.fetchone()

        if existing:
            if existing["status"] == "accepted":
                return {"message": "You are already connected.", "status": "accepted"}
            if existing["requester_id"] == me["id"]:
                return {"message": "Connection request already pending.", "status": "pending_outgoing"}

            await db.execute("UPDATE connections SET status = 'accepted' WHERE id = ?", (existing["id"],))
            await db.commit()
            return {"message": "Connection established!", "status": "accepted"}

        await db.execute(
            "INSERT INTO connections (requester_id, receiver_id, status) VALUES (?, ?, 'pending')",
            (me["id"], target["id"])
        )
        await db.commit()

    return {"message": "Connection request sent!", "status": "pending_outgoing"}


@router.post("/connections/{target_username}/accept")
async def accept_connection(target_username: str, current_user: dict = Depends(require_auth)):
    """Accept an incoming connection request."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("SELECT id FROM users WHERE username = ?", (target_username,)) as cursor:
            target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        async with db.execute("""
            SELECT id FROM connections
            WHERE requester_id = ? AND receiver_id = ? AND status = 'pending'
        """, (target["id"], me["id"])) as cursor:
            request_row = await cursor.fetchone()

        if not request_row:
            raise HTTPException(status_code=404, detail="Pending request not found")

        await db.execute("UPDATE connections SET status = 'accepted' WHERE id = ?", (request_row["id"],))
        await db.commit()

    return {"message": "Connection accepted!", "status": "accepted"}


@router.delete("/connections/{target_username}")
async def handle_connection_removal(target_username: str, current_user: dict = Depends(require_auth)):
    """A master route to Refuse (incoming), Undo (outgoing), or Unfriend (accepted)."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("SELECT id FROM users WHERE username = ?", (target_username,)) as cursor:
            target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        await db.execute("""
            DELETE FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))

        await db.commit()

    return {"message": "Connection removed or request canceled.", "status": "none"}


@router.get("/connections/pending")
async def get_pending_requests(current_user: dict = Depends(require_auth)):
    """Fetch all incoming connection requests for the logged-in user."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("""
            SELECT u.username as requester_username, c.created_at
            FROM connections c
            JOIN users u ON c.requester_id = u.id
            WHERE c.receiver_id = ? AND c.status = 'pending'
        """, (me["id"],)) as cursor:
            requests = await cursor.fetchall()

    return {
        "requests": [{"username": r["requester_username"], "date": r["created_at"]} for r in requests]
    }


@router.get("/connections/inbox")
async def get_inbox(current_user: dict = Depends(require_auth)):
    """Get active chats/connections and their last messages."""
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],)) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User session is invalid or account no longer exists.")

        async with db.execute("""
            SELECT CASE WHEN c.requester_id = ? THEN c.receiver_id ELSE c.requester_id END AS contact_id
            FROM connections c
            WHERE c.status = 'accepted'
              AND (c.requester_id = ? OR c.receiver_id = ?)
        """, (me["id"], me["id"], me["id"])) as cursor:
            accepted_rows = await cursor.fetchall()

        inbox = []
        for row in accepted_rows:
            contact_id = row["contact_id"]

            async with db.execute("SELECT username FROM users WHERE id = ?", (contact_id,)) as contact_cursor:
                contact_user = await contact_cursor.fetchone()
            if not contact_user:
                continue

            async with db.execute("""
                SELECT sender_id, content, timestamp
                FROM messages
                WHERE (sender_id = ? AND receiver_id = ?)
                   OR (sender_id = ? AND receiver_id = ?)
                ORDER BY timestamp DESC
                LIMIT 1
            """, (me["id"], contact_id, contact_id, me["id"])) as message_cursor:
                last_row = await message_cursor.fetchone()

            inbox.append({
                "username": contact_user["username"],
                "last_message": last_row["content"] if last_row else "",
                "last_message_at": last_row["timestamp"] if last_row else None,
            })

    inbox.sort(key=lambda item: item["last_message_at"] or "", reverse=True)
    return {"inbox": inbox}
