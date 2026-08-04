import aiosqlite
from app.core.security import DB_FILE_NAME

async def init_db():
    async with aiosqlite.connect(DB_FILE_NAME) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        # Users Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Connections Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(requester_id, receiver_id),
                CHECK(requester_id != receiver_id), -- Prevent self-requests at DB level
                FOREIGN KEY (requester_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # Messages Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id, receiver_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_connections_users ON connections(requester_id, receiver_id);")

        await db.commit()

async def get_user_id(db: aiosqlite.Connection, username: str) -> int | None:
    """Helper to fetch user ID by username."""
    async with db.execute("SELECT id FROM users WHERE username = ?", (username,)) as cursor:
        row = await cursor.fetchone()
        return row["id"] if row else None
