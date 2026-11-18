from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    return create_engine(
        url,
        pool_pre_ping=True,  # survive sleeping/suspended free-tier databases
        pool_size=5,
        max_overflow=5,
        pool_recycle=280,
        connect_args={"connect_timeout": 10},
    )


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
