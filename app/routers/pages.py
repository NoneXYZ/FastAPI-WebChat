import aiosqlite
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.security import DB_FILE_NAME
from app.core.security import COOKIE_NAME, decode_jwt, require_guest, require_auth

templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter(tags=["Pages"])

import aiosqlite
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.security import DB_FILE_NAME, COOKIE_NAME, decode_jwt

templates = Jinja2Templates(directory="frontend/templates")
router = APIRouter(tags=["Pages"])

@router.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    user_payload = None

    if token:
        payload = decode_jwt(token)
        if payload:
            username = payload.get("username")
            
            async with aiosqlite.connect(DB_FILE_NAME) as db:
                db.row_factory = aiosqlite.Row # Enables column string lookups
                async with db.execute("SELECT id FROM users WHERE username = ?", (username,)) as cursor:
                    user_row = await cursor.fetchone()
            
            if user_row:
                user_payload = {
                    "id": user_row["id"],
                    "username": username
                }

    if not user_payload:
        return templates.TemplateResponse(request=request, name="index.html")

    return templates.TemplateResponse(
        request=request,
        name="root.html",
        context={
            "id": user_payload.get("id"), 
            "username": user_payload.get("username")
        }
    )


@router.get("/register", response_class=HTMLResponse, dependencies=[Depends(require_guest)])
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@router.get("/login", response_class=HTMLResponse, dependencies=[Depends(require_guest)])
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@router.get("/search", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def chat_page(request: Request, current_user: dict = Depends(require_auth)):
    return templates.TemplateResponse(request=request, name="search.html")

@router.get("/inbox", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def inbox_page(request: Request, current_user: dict = Depends(require_auth)):
    return templates.TemplateResponse(request=request, name="inbox.html")

# ...

@router.get("/profile/{username}", response_class=HTMLResponse)
async def user_profile_page(username: str, request: Request):
    token = request.cookies.get(COOKIE_NAME)
    user_payload = decode_jwt(token) if token else None
    
    viewer_id = user_payload.get("id") if user_payload else None
    viewer_name = user_payload.get("username") if user_payload else None

    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,))
        profile_user = await cursor.fetchone()
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")

        relationship = "none" 
        
        if viewer_id:
            if viewer_id == profile_user["id"]:
                relationship = "self"
            else:
                conn_cursor = await db.execute("""
                    SELECT requester_id, status FROM connections
                    WHERE (requester_id = ? AND receiver_id = ?)
                       OR (requester_id = ? AND receiver_id = ?)
                """, (viewer_id, profile_user["id"], profile_user["id"], viewer_id))
                connection = await conn_cursor.fetchone()

                if connection:
                    if connection["status"] == "accepted":
                        relationship = "connected"
                    elif connection["requester_id"] == viewer_id:
                        relationship = "pending_outgoing"
                    else:
                        relationship = "pending_incoming"

        connection_count_cursor = await db.execute("""
            SELECT COUNT(*) AS total FROM connections
            WHERE status = 'accepted' AND (requester_id = ? OR receiver_id = ?)
        """, (profile_user["id"], profile_user["id"]))
        connection_count = await connection_count_cursor.fetchone()

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "id": viewer_id,
            "viewer_name": viewer_name,
            "profile_user": {
                "username": profile_user["username"],
                "created_at": profile_user["created_at"],
            },
            "relationship": relationship, # Can be: "self", "none", "connected", "pending_outgoing", "pending_incoming"
            "connection_count": connection_count["total"] if connection_count else 0,
        }
    )
