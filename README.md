# LocalChat

LocalChat is a private, connection-based web chat application. Users can find people by username, send or accept connection requests, and exchange messages in real time.

![Dashboard preview](src/Dashboard.png)

![Messages preview](src/Messages.png)

## Highlights

- Cookie-based authentication with registration and login
- User search, connection requests, notifications, and profiles
- Dedicated inbox and per-user chat routes
- REST-backed chat history with WebSocket delivery for live messages
- Responsive dark/light interface

## Stack

- Backend: FastAPI, SQLite with `aiosqlite`, Pydantic, PyJWT, and WebSockets
- Frontend: Server-rendered Jinja templates, vanilla JavaScript, and CSS

## Run locally

1. Create and activate a virtual environment.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies.

   ```bash
   pip install -r requirements.txt
   ```

3. Configure `.env` with a secure `JWT_SECRET_KEY`. You can also set `APP_NAME`, `PORT`, and `DB_FILE_NAME`.

4. Start the application.

   ```bash
   uvicorn app.main:app --reload
   ```

5. Open `http://127.0.0.1:8000`.

The database is created automatically at the path configured by `DB_FILE_NAME` when the app starts.

## Credits

The backend was made by the project author. The frontend was made by Codex.
