"""
Development server entry point.

Usage:
    py run.py                          # auto-reload on file changes
    uvicorn app.main:app --port 8081   # manual uvicorn

Production:
    uvicorn app.main:app --host 0.0.0.0 --port 8081 --workers 4
"""
import uvicorn
from app.config.settings import settings


if __name__ == "__main__":
    print(f"""
  ForYou API - Starting up
  App  : http://{settings.APP_HOST}:{settings.APP_PORT}
  Docs : http://localhost:{settings.APP_PORT}/docs
  DB   : {settings.DB_HOST}:{settings.DB_PORT}
    """)
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True,
    )
