"""Verify Session 2: authentication and protected routes."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from fastapi.testclient import TestClient

from app import create_app
from app.database.connection import SessionLocal, init_db
from app.models.admin import Admin
from app.services.auth_service import create_admin, get_admin_by_username
from app.utils.config import get_settings


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    init_db()

    db = SessionLocal()
    try:
        test_user = "_verify_admin_"
        existing = get_admin_by_username(db, test_user)
        if existing:
            db.delete(existing)
            db.commit()
        create_admin(db, test_user, "verify-test-pass-123")
        password = "verify-test-pass-123"
    finally:
        db.close()

    app = create_app()
    client = TestClient(app)

    # Unauthenticated dashboard redirects to login
    response = client.get("/dashboard", follow_redirects=False)
    if response.status_code not in (303, 307):
        print(f"FAIL: /dashboard should redirect, got {response.status_code}")
        return 1

    # Login page accessible
    response = client.get("/login")
    if response.status_code != 200:
        print(f"FAIL: /login should return 200, got {response.status_code}")
        return 1

    # Bad credentials rejected
    response = client.post(
        "/login",
        data={"username": test_user, "password": "wrong"},
        follow_redirects=False,
    )
    if response.status_code != 401:
        print(f"FAIL: bad login should return 401, got {response.status_code}")
        return 1

    # Good credentials create session
    response = client.post(
        "/login",
        data={"username": test_user, "password": password},
        follow_redirects=False,
    )
    if response.status_code != 303:
        print(f"FAIL: good login should redirect 303, got {response.status_code}")
        return 1

    # Dashboard accessible with session cookie
    response = client.get("/dashboard")
    if response.status_code != 200:
        print(f"FAIL: authenticated /dashboard should return 200, got {response.status_code}")
        return 1
    if "Dashboard" not in response.text:
        print("FAIL: dashboard HTML missing expected content")
        return 1

    # Logout clears session
    response = client.post("/logout", follow_redirects=False)
    if response.status_code != 303:
        print(f"FAIL: logout should redirect 303, got {response.status_code}")
        return 1

    response = client.get("/dashboard", follow_redirects=False)
    if response.status_code not in (303, 307):
        print(f"FAIL: post-logout /dashboard should redirect, got {response.status_code}")
        return 1

    # Cleanup test admin
    db = SessionLocal()
    try:
        admin = get_admin_by_username(db, test_user)
        if admin:
            db.delete(admin)
            db.commit()
    finally:
        db.close()

    print("Session 2 auth verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
