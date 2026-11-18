from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import analytics, assistant, auth, budgets, categories, health, reports, savings, transactions, uploads, users
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Seed system categories if migrations ran but seed data is missing (idempotent).
    try:
        from app.core.database import SessionLocal
        from app.services.categories import ensure_default_categories

        with SessionLocal() as db:
            ensure_default_categories(db)
    except Exception:  # database may be asleep on free tiers; health endpoint reports it
        import logging

        logging.getLogger("financemate").warning("could not verify default categories at startup")
    yield


docs = not settings.is_production
app = FastAPI(
    title="AI FinanceMate API",
    version="1.0.0",
    description="Personal finance management with the JOCASTA multi-agent assistant.",
    docs_url="/api/docs" if docs else None,
    redoc_url="/api/redoc" if docs else None,
    openapi_url="/api/openapi.json" if docs else None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


register_error_handlers(app)

api = APIRouter(prefix="/api/v1")
for r in (health, auth, users, categories, transactions, budgets, savings, analytics, reports, uploads, assistant):
    api.include_router(r.router)
app.include_router(api)


@app.get("/")
def root():
    return {"name": "AI FinanceMate API", "health": "/api/v1/health"}
