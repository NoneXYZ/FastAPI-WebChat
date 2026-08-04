import aiosqlite
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.security import DB_FILE_NAME
from app.models import UserCredentials
from app.core.security import create_access_token, require_auth, COOKIE_NAME, ACCESS_TOKEN_EXPIRE_DAYS

router = APIRouter(tags=["Authentication"])
password_hash = PasswordHash((BcryptHasher(),))

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCredentials):
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        async with db.execute("SELECT id FROM users WHERE username = ?", (user.username,)) as cursor:
            if await cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username Already Registered")

        hashed_pwd = get_password_hash(user.password)
        await db.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (user.username, hashed_pwd))
        await db.commit()

        return {"message": "User registered successfully!"}

@router.post("/login")
async def login_user(credentials: UserCredentials):
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id, username, hashed_password FROM users WHERE username = ?", (credentials.username,)) as cursor:
           user = await cursor.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid username or password")
            
        if not password_hash.verify(credentials.password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        access_token = create_access_token(
            data={"sub": user["username"], "id": user["id"], "username": user["username"]}
        )

        response = JSONResponse(content={"message": "Login successful!"})
        response.set_cookie(
            key=COOKIE_NAME,
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )

        return response

@router.post("/logout", dependencies=[Depends(require_auth)])
async def logout_user(request: Request):
    """Invalidate the auth cookie and log the user out."""
    logout_response = JSONResponse(content={"message": "Logged out successfully!"})
    logout_response.delete_cookie(key=COOKIE_NAME, path="/")
    return logout_response