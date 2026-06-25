"""Create or update an admin account."""

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.database.connection import SessionLocal
from app.services.auth_service import create_admin, get_admin_by_username, hash_password


def main() -> int:
    username = input("Admin username: ").strip()
    if not username:
        print("Username required.")
        return 1

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return 1
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1

    db = SessionLocal()
    try:
        existing = get_admin_by_username(db, username)
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            db.commit()
            print(f"Updated password for admin '{username}'.")
        else:
            create_admin(db, username, password)
            print(f"Created admin '{username}'.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
