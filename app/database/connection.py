from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.utils.config import get_settings
from app.utils.logging import log_exception

settings = get_settings()

engine_kwargs: dict = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "echo": settings.debug,
}

if settings.db_driver == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.resolved_database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        db.rollback()
        log_exception("database", "Database session error", exc)
        raise
    finally:
        db.close()


from app.database.init_db import init_db  # noqa: E402

__all__ = ["engine", "SessionLocal", "get_db", "init_db"]
