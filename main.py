from contextlib import asynccontextmanager
import inspect
from typing import Dict, List
from fastapi import FastAPI, Request, HTTPException, status, APIRouter, Depends, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from models import UserCreate, UserLogin, MessageCreate
from database import DB_FILE, init_db
from auth import create_access_token, require_guest, require_auth, decode_jwt, COOKIE_NAME
import aiosqlite
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

class ChatConnectionManager:
    def __init__(self):
        # Maps username -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        if username not in self.active_connections:
            self.active_connections[username] = []
        self.active_connections[username].append(websocket)

    def disconnect(self, username: str, websocket: WebSocket):
        if username in self.active_connections:
            self.active_connections[username].remove(websocket)
            if not self.active_connections[username]:
                del self.active_connections[username]

    async def send_private_message(self, message: dict, sender: str, receiver: str, current_ws: WebSocket | None = None):
        """Sends a message to both the sender and receiver if they are online."""
        payload = json.dumps(message)

        if receiver in self.active_connections:
            for connection in list(self.active_connections[receiver]):
                if connection is not current_ws:
                    await connection.send_text(payload)

        if sender in self.active_connections:
            for connection in list(self.active_connections[sender]):
                if connection is not current_ws:
                    await connection.send_text(payload)

manager = ChatConnectionManager()

app = FastAPI(lifespan=lifespan)
password_hash = PasswordHash((BcryptHasher(),))

# Mounting Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Password Helper
def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

# Routers
guest_router = APIRouter(dependencies=[Depends(require_guest)])
auth_router = APIRouter(dependencies=[Depends(require_auth)])


# --- ROOT ROUTE ---
@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    user_payload = decode_jwt(token) if token else None

    if not user_payload:
        return templates.TemplateResponse(request=request, name="index.html")

    return templates.TemplateResponse(
        request=request, 
        name="root.html", 
        context={"request": request, "username": user_payload["sub"]}
    )


# --- GUEST ROUTES & APIS ---
@guest_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@guest_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@guest_router.post("/api/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id FROM users WHERE username = ?", (user.username,)) as cursor:
            if await cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username Already Registered")

        hashed_pwd = get_password_hash(user.password)
        await db.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (user.username, hashed_pwd))
        await db.commit()

        return {"message": "User registered successfully!"}

@guest_router.post("/api/login")
async def login_user(credentials: UserLogin):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id, username, hashed_password FROM users WHERE username = ?", (credentials.username,)) as cursor:
            user = await cursor.fetchone()

        if not user or not password_hash.verify(credentials.password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        access_token = create_access_token(data={"sub": user["username"]})

        response = JSONResponse(content={"message": "Login successful!"})
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=7 * 24 * 60 * 60
        )

        return response


@app.get("/profile/{username}", response_class=HTMLResponse)
async def user_profile_page(request: Request, username: str):
    token = request.cookies.get(COOKIE_NAME)
    user_payload = decode_jwt(token) if token else None

    if not user_payload:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,))
        profile_user = await cursor.fetchone()
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")

        viewer_cursor = await db.execute("SELECT id, username FROM users WHERE username = ?", (user_payload["sub"],))
        viewer = await viewer_cursor.fetchone()

        relationship = "self"
        if viewer and viewer["id"] != profile_user["id"]:
            conn_cursor = await db.execute("""
                SELECT requester_id, status
                FROM connections
                WHERE (requester_id = ? AND receiver_id = ?)
                   OR (requester_id = ? AND receiver_id = ?)
            """, (viewer["id"], profile_user["id"], profile_user["id"], viewer["id"]))
            connection = await conn_cursor.fetchone()

            if not connection:
                relationship = "none"
            elif connection["status"] == "accepted":
                relationship = "connected"
            elif connection["requester_id"] == viewer["id"]:
                relationship = "pending_outgoing"
            else:
                relationship = "pending_incoming"

        connection_count_cursor = await db.execute("""
            SELECT COUNT(*) AS total
            FROM connections
            WHERE status = 'accepted'
              AND (requester_id = ? OR receiver_id = ?)
        """, (profile_user["id"], profile_user["id"]))
        connection_count = await connection_count_cursor.fetchone()

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "profile_user": {
                "username": profile_user["username"],
                "created_at": profile_user["created_at"],
            },
            "viewer_name": user_payload["sub"],
            "relationship": relationship,
            "connection_count": connection_count["total"] if connection_count else 0,
        }
    )


@auth_router.post("/api/logout")
async def logout_user(response: Response, current_user: dict = Depends(require_auth)):
    """Invalidate the auth cookie and log the user out."""
    logout_response = JSONResponse(content={"message": "Logged out successfully!"})
    logout_response.delete_cookie(key=COOKIE_NAME, path="/")
    return logout_response


# --- AUTHENTICATED APIS: USERS ---
@auth_router.get("/api/users/search")
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


# --- AUTHENTICATED APIS: CONNECTIONS ---

@auth_router.get("/api/connections/status/{target_username}")
async def get_connection_status(target_username: str, current_user: dict = Depends(require_auth)):
    """Helper to tell the frontend exactly what relationship the two users have."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if me["id"] == target["id"]:
            return {"status": "self"}

        cursor = await db.execute("""
            SELECT requester_id, status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))
        conn = await cursor.fetchone()

        if not conn:
            return {"status": "none"}
        if conn["status"] == "accepted":
            return {"status": "accepted"}
        if conn["requester_id"] == me["id"]:
            return {"status": "pending_outgoing"} # You sent request to them
        
        return {"status": "pending_incoming"} # They sent request to you


@auth_router.post("/api/connections/{target_username}")
async def send_connection_request(target_username: str, current_user: dict = Depends(require_auth)):
    """Send a connection request. Auto-accepts if they already sent one to you."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if me["id"] == target["id"]:
            raise HTTPException(status_code=400, detail="You cannot connect with yourself")

        cursor = await db.execute("""
            SELECT id, requester_id, status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))
        existing = await cursor.fetchone()

        if existing:
            if existing["status"] == "accepted":
                return {"message": "You are already connected.", "status": "accepted"}
            if existing["requester_id"] == me["id"]:
                return {"message": "Connection request already pending.", "status": "pending_outgoing"}
            
            # If they already sent us a request, smart-accept it instead of crashing
            await db.execute("UPDATE connections SET status = 'accepted' WHERE id = ?", (existing["id"],))
            await db.commit()
            return {"message": "Connection established!", "status": "accepted"}

        await db.execute(
            "INSERT INTO connections (requester_id, receiver_id, status) VALUES (?, ?, 'pending')",
            (me["id"], target["id"])
        )
        await db.commit()

    return {"message": "Connection request sent!", "status": "pending_outgoing"}


@auth_router.post("/api/connections/{target_username}/accept")
async def accept_connection(target_username: str, current_user: dict = Depends(require_auth)):
    """Accept an incoming connection request."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        # Ensure we are the receiver of this pending request
        cursor = await db.execute("""
            SELECT id FROM connections
            WHERE requester_id = ? AND receiver_id = ? AND status = 'pending'
        """, (target["id"], me["id"]))
        request_row = await cursor.fetchone()

        if not request_row:
            raise HTTPException(status_code=404, detail="Pending request not found")

        await db.execute("UPDATE connections SET status = 'accepted' WHERE id = ?", (request_row["id"],))
        await db.commit()

    return {"message": "Connection accepted!", "status": "accepted"}


@auth_router.delete("/api/connections/{target_username}")
async def handle_connection_removal(target_username: str, current_user: dict = Depends(require_auth)):
    """A master route to Refuse (incoming), Undo (outgoing), or Unfriend (accepted)."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        # Safely delete any connection link between these two users regardless of state
        await db.execute("""
            DELETE FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))
        
        await db.commit()

    return {"message": "Connection removed or request canceled.", "status": "none"}


@auth_router.get("/api/connections/pending")
async def get_pending_requests(current_user: dict = Depends(require_auth)):
    """Fetch all incoming connection requests for the logged-in user."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("""
            SELECT u.username as requester_username, c.created_at
            FROM connections c
            JOIN users u ON c.requester_id = u.id
            WHERE c.receiver_id = ? AND c.status = 'pending'
        """, (me["id"],))
        requests = await cursor.fetchall()

    return {
        "requests": [{"username": r["requester_username"], "date": r["created_at"]} for r in requests]
    }


@auth_router.get("/api/connections/inbox")
async def get_inbox(current_user: dict = Depends(require_auth)):
    """Get active chats/connections and their last messages."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=401, detail="User is no longer available")

        cursor = await db.execute("""
            SELECT CASE WHEN c.requester_id = ? THEN c.receiver_id ELSE c.requester_id END AS contact_id
            FROM connections c
            WHERE c.status = 'accepted'
              AND (c.requester_id = ? OR c.receiver_id = ?)
        """, (me["id"], me["id"], me["id"]))
        accepted_rows = await cursor.fetchall()

        inbox = []
        for row in accepted_rows:
            contact_id = row["contact_id"]

            contact = await db.execute("SELECT username FROM users WHERE id = ?", (contact_id,))
            contact_user = await contact.fetchone()

            last_message = await db.execute("""
                SELECT sender_id, content, timestamp
                FROM messages
                WHERE (sender_id = ? AND receiver_id = ?)
                   OR (sender_id = ? AND receiver_id = ?)
                ORDER BY timestamp DESC
                LIMIT 1
            """, (me["id"], contact_id, contact_id, me["id"]))
            last_row = await last_message.fetchone()

            inbox.append({
                "username": contact_user["username"],
                "last_message": last_row["content"] if last_row else "",
                "last_message_at": last_row["timestamp"] if last_row else None,
            })

    inbox.sort(key=lambda item: item["last_message_at"] or "", reverse=True)
    return {"inbox": inbox}


# --- AUTHENTICATED APIS: MESSAGING ---

@auth_router.post("/api/messages/{target_username}")
async def send_message(target_username: str, message: MessageCreate, current_user: dict = Depends(require_auth)):
    """Saves a message only if the users have an accepted connection."""
    if not message.content or not message.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        cursor = await db.execute("""
            SELECT status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))

        connection = await cursor.fetchone()
        if not connection or connection["status"] != "accepted":
            raise HTTPException(status_code=403, detail="You can only message accepted connections.")

        await db.execute(
            "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
            (me["id"], target["id"], message.content.strip())
        )
        await db.commit()

    return {"message": "Message sent!"}


@auth_router.get("/api/messages/{target_username}")
async def get_messages(target_username: str, current_user: dict = Depends(require_auth)):
    """Fetches messages only when the users have an accepted connection."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_user["sub"],))
        me = await cursor.fetchone()

        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
        target = await cursor.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        cursor = await db.execute("""
            SELECT status FROM connections
            WHERE (requester_id = ? AND receiver_id = ?)
               OR (requester_id = ? AND receiver_id = ?)
        """, (me["id"], target["id"], target["id"], me["id"]))

        connection = await cursor.fetchone()

        if not connection or connection["status"] != "accepted":
            return {
                "messages": [],
                "status": "blocked",
                "detail": "You must accept the connection to view messages."
            }

        cursor = await db.execute("""
            SELECT sender_id, content, timestamp
            FROM messages
            WHERE (sender_id = ? AND receiver_id = ?)
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp ASC
        """, (me["id"], target["id"], target["id"], me["id"]))

        messages = await cursor.fetchall()

        formatted_messages = [
            {
                "sender": current_user["sub"] if msg["sender_id"] == me["id"] else target_username,
                "content": msg["content"],
                "timestamp": msg["timestamp"]
            }
            for msg in messages
        ]

    return {"messages": formatted_messages, "status": "connected"}

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    # 1. Authenticate via cookie
    token = websocket.cookies.get(COOKIE_NAME)
    user_payload = decode_jwt(token) if token else None
    
    if not user_payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    current_username = user_payload["sub"]
    
    # 2. Get DB connection for initial validation
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (current_username,))
        me = await cursor.fetchone()
        if not me:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        my_id = me["id"]

    # 3. Register with Connection Manager
    await manager.connect(current_username, websocket)
    
    try:
        while True:
            # 4. Receive data
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
                target_username = payload.get("receiver", "").strip()
                content = payload.get("content", "").strip()
            except json.JSONDecodeError:
                continue
                
            if not content or not target_username:
                continue
            
            # 5. Open short DB transaction per message
            async with aiosqlite.connect(DB_FILE) as db:
                db.row_factory = aiosqlite.Row
                
                # Fetch target user ID
                cursor = await db.execute("SELECT id FROM users WHERE username = ?", (target_username,))
                target = await cursor.fetchone()
                if not target:
                    await websocket.send_json({"error": "User not found"})
                    continue
                    
                target_id = target["id"]
                
                # Verify friendship status
                cursor = await db.execute("""
                    SELECT status FROM connections
                    WHERE (requester_id = ? AND receiver_id = ?)
                       OR (requester_id = ? AND receiver_id = ?)
                """, (my_id, target_id, target_id, my_id))
                
                connection = await cursor.fetchone()
                if not connection or connection["status"] != "accepted":
                    await websocket.send_json({"error": "You are not friends with this user"})
                    continue
                
                # 6. Save message
                await db.execute(
                    "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                    (my_id, target_id, content)
                )
                await db.commit()
            
            # 7. Broadcast via manager
            message_out = {
                "sender": current_username,
                "receiver": target_username,
                "content": content,
            }
            
            await manager.send_private_message(
                message=message_out, 
                sender=current_username, 
                receiver=target_username, 
                current_ws=websocket
            )
            
    except WebSocketDisconnect:
        pass
    finally:
        # Guaranteed cleanup regardless of error type
        res = manager.disconnect(current_username, websocket)
        if inspect.isawaitable(res):
            await res

# Include Routers
app.include_router(guest_router)
app.include_router(auth_router)