"""Verify Session 1: database connection and required tables."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import inspect, text

from app.database.connection import engine, init_db
from app.utils.config import get_settings


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()

    print(f"DB driver: {settings.db_driver}")
    safe_url = settings.resolved_database_url.replace(settings.db_password, "***")
    print(f"DB URL: {safe_url}")

    init_db()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    required = {"users", "detections", "unknown_faces", "admins"}
    missing = required - set(tables)

    print(f"Tables: {tables}")
    if missing:
        print(f"MISSING: {sorted(missing)}")
        return 1

    print("Session 1 DB verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
