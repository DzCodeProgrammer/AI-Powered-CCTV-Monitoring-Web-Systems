"""Build face embeddings from registered users in the database."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.database.connection import SessionLocal, init_db
from app.services.recognition_service import rebuild_embeddings
from app.utils.config import get_settings


def main() -> int:
    get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    try:
        store = rebuild_embeddings(db)
        print(f"Built {len(store.entries)} embeddings.")
        for entry in store.entries:
            print(f"  - {entry.name} (user_id={entry.user_id})")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
