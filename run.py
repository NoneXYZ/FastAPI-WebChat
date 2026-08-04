from app.core.security import PORT

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", port=PORT, reload=True, reload_dirs=["app"])
