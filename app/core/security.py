from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
import aiosqlite
import jwt
import os

current_file = Path(__file__).resolve()
base_dir = current_file.parent.parent.parent
env_path = base_dir / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)

COOKIE_NAME = os.getenv("COOKIE_NAME", "my_app_cookie")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "YOUR_GENERATED_32_CHARACTER_HEX_KEY")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRES_IN", "7"))
DB_FILE_NAME = os.getenv("DB_FILE_NAME", "app.db")
PORT = int(os.getenv("PORT", 8000))
ALGORITHM = "HS256"

def create_access_token(data: dict) -> str:
    to_encode = dict(data)
    if "sub" not in to_encode:
        if "username" in to_encode:
            to_encode["sub"] = to_encode["username"]
        elif "email" in to_encode:
            to_encode["sub"] = to_encode["email"]

    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


async def require_auth(request: Request) -> dict:
    """Guard for protected routes/APIs."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_jwt(token)

    if not token or not payload:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )

    username = payload.get("username")
    if username:
        async with aiosqlite.connect(DB_FILE_NAME) as db:
            async with db.execute("SELECT id FROM users WHERE username = ?", (username,)) as cursor:
                user_row = await cursor.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User session is invalid or account no longer exists."
            )

    return payload


async def require_guest(request: Request) -> None:
    """Guard for guest-only pages/APIs. Redirects active users to home."""
    token = request.cookies.get(COOKIE_NAME)
    
    if token:
        payload = decode_jwt(token)
        if payload:
            username = payload.get("username")
            
            async with aiosqlite.connect(DB_FILE_NAME) as db:
                async with db.execute("SELECT 1 FROM users WHERE username = ?", (username,)) as cursor:
                    user_exists = await cursor.fetchone()
            
            if user_exists:
                raise HTTPException(
                    status_code=status.HTTP_303_SEE_OTHER,
                    headers={"Location": "/"}
                )
                
    return None
