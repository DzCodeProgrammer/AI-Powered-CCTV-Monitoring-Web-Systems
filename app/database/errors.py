"""Database error handling helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.utils.logging import log_exception

T = TypeVar("T")


def rollback_db(db: Session) -> None:
    try:
        db.rollback()
    except SQLAlchemyError:
        pass


def safe_commit(db: Session, operation: str = "database commit") -> bool:
    try:
        db.commit()
        return True
    except SQLAlchemyError as exc:
        rollback_db(db)
        log_exception("database", f"{operation} failed", exc)
        return False


def run_db_operation(
    db: Session,
    operation: str,
    fn: Callable[[], T],
    default: T | None = None,
) -> T | None:
    try:
        return fn()
    except SQLAlchemyError as exc:
        rollback_db(db)
        log_exception("database", f"{operation} failed", exc)
        return default
