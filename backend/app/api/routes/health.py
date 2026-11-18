from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception:
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unavailable",
            "llm_configured": settings.llm_configured, "environment": settings.APP_ENV}
    return JSONResponse(body, status_code=200 if db_ok else 503)
