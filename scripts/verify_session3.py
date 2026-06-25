"""Verify Session 3: face registration module."""

import io
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import create_app
from app.database.connection import SessionLocal, init_db
from app.models.user import User
from app.services.auth_service import create_admin, get_admin_by_username
from app.utils.config import get_settings


def make_test_image() -> bytes:
    image = Image.new("RGB", (128, 128), color=(70, 130, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    init_db()

    admin_user = "_verify_reg_admin_"
    person_name = "_Verify Person S3_"
    db = SessionLocal()
    try:
        existing_admin = get_admin_by_username(db, admin_user)
        if existing_admin:
            db.delete(existing_admin)
        existing_person = db.scalar(select(User).where(User.name == person_name))
        if existing_person:
            if Path(existing_person.image_path).is_file():
                Path(existing_person.image_path).unlink()
            db.delete(existing_person)
        db.commit()
        create_admin(db, admin_user, "verify-reg-pass-123")
    finally:
        db.close()

    client = TestClient(create_app())
    client.post(
        "/login",
        data={"username": admin_user, "password": "verify-reg-pass-123"},
        follow_redirects=False,
    )

    # Registration page requires auth
    response = client.get("/dashboard/register")
    if response.status_code != 200:
        print(f"FAIL: register page returned {response.status_code}")
        return 1

    # Unauthenticated blocked
    anon = TestClient(create_app())
    response = anon.get("/dashboard/register", follow_redirects=False)
    if response.status_code not in (303, 307):
        print(f"FAIL: unauthenticated register should redirect, got {response.status_code}")
        return 1

    # Register person with image upload
    image_bytes = make_test_image()
    response = client.post(
        "/dashboard/register",
        data={"name": person_name},
        files={"image": ("verify_face.jpg", image_bytes, "image/jpeg")},
        follow_redirects=False,
    )
    if response.status_code != 303:
        print(f"FAIL: registration should redirect 303, got {response.status_code}")
        print(response.text[:500])
        return 1

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.name == person_name))
        if not user:
            print("FAIL: user not found in database")
            return 1
        if not Path(user.image_path).is_file():
            print(f"FAIL: image file missing at {user.image_path}")
            return 1
        if not user.image_path.startswith(f"{settings.dataset_dir}/"):
            print(f"FAIL: image not in datasets folder: {user.image_path}")
            return 1
        image_path = user.image_path
    finally:
        db.close()

    # Dataset image served to authenticated admin
    filename = Path(image_path).name
    response = client.get(f"/dashboard/datasets/{filename}")
    if response.status_code != 200:
        print(f"FAIL: dataset image route returned {response.status_code}")
        return 1

    # Duplicate name rejected
    response = client.post(
        "/dashboard/register",
        data={"name": person_name},
        files={"image": ("verify_face.jpg", image_bytes, "image/jpeg")},
        follow_redirects=False,
    )
    if response.status_code != 400:
        print(f"FAIL: duplicate name should return 400, got {response.status_code}")
        return 1

    # Cleanup
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.name == person_name))
        if user:
            if Path(user.image_path).is_file():
                Path(user.image_path).unlink()
            db.delete(user)
        admin = get_admin_by_username(db, admin_user)
        if admin:
            db.delete(admin)
        db.commit()
    finally:
        db.close()

    print("Session 3 registration verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
