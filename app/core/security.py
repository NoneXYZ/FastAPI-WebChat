from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
import jwt

current_file = Path(__file__).resolve()
base_dir = current_file.parent.parent.parent
env_path = base_dir / ".env"
load_dotenv(dotenv_path=env_path)

COOKIE_NAME = os.getenv("COOKIE_NAME", "access_token")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"


def _get_access_token_expire_days() -> int:
    raw_value = os.getenv("JWT_EXPIRES_IN", "7")
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 7


ACCESS_TOKEN_EXPIRE_DAYS = _get_access_token_expire_days()


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


def require_auth(request: Request) -> dict:
    """Guard for protected routes/APIs."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_jwt(token)
    
    if not token or not payload:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return payload


def require_guest(request: Request) -> None:
    """Guard for guest-only pages/APIs."""
    token = request.cookies.get(COOKIE_NAME)
    if token and decode_jwt(token):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"}
        )
    return None