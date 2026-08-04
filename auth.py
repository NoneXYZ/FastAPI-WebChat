from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status
import jwt
from pydantic import SecretStr

# Configuration
SECRET_KEY = SecretStr("aetherchat_secret_key_super_secure_32chars_long")
ALGORITHM = "HS256"
COOKIE_NAME = "access_token"

def create_access_token(data: dict) -> str:
    """Creates a signed JWT string."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    to_encode.update({"exp": expire, "action": "auth"})
    return jwt.encode(to_encode, SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)

def decode_jwt(token: str) -> dict | None:
    """Validates and decodes the token, handling the 'Bearer ' prefix."""
    try:
        # 2. Strip "Bearer " out if present so PyJWT can read it cleanly
        if token.startswith("Bearer "):
            token = token.replace("Bearer ", "", 1)
            
        return jwt.decode(token, SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# --- GUARD 1: FOR PROTECTED PAGES (e.g., /chat) ---
def require_auth(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token or not decode_jwt(token):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return decode_jwt(token)

# --- GUARD 2: FOR GUEST-ONLY PAGES (e.g., /login, /register) ---
def require_guest(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token and decode_jwt(token):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"}
        )
    return None
