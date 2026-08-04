import aiosqlite
from fastapi import APIRouter, Depends
from fastapi.templating import Jinja2Templates

from app.database import DB_FILE
from app.core.security import require_auth

templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["Users"])

@router.get("/users/search")
async def search_users(q: str = "", current_user: dict = Depends(require_auth)):
    if not q or len(q.strip()) == 0:
        return {"results": []}
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            "SELECT id, username FROM users WHERE username LIKE ? AND username != ? LIMIT 10",
            (f"%{q}%", current_user["sub"])
        )
        users = await cursor.fetchall()

    return {"results": [{"id": u["id"], "username": u["username"]} for u in users]}
