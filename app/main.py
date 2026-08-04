from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import pages
from app.APIs import auth, connections, users, messages
from app.websockets import endpoints as websocket
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)

app.include_router(websocket.router, tags=["WebSockets"])

app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(connections.router, prefix="/api", tags=["Connections"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
