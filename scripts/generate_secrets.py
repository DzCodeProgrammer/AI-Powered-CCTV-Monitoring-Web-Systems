"""Generate secure secrets for local .env (never commit output)."""

import secrets
import string
from pathlib import Path


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_secret_key(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    example = project_root / ".env.example"
    target = project_root / ".env"

    if not example.exists():
        raise SystemExit(".env.example not found")

    content = example.read_text(encoding="utf-8")
    replacements = {
        "change-this-to-a-random-secret-key": generate_secret_key(),
        "change-this-mysql-root-password": generate_password(),
        "change-this-cctv-db-password": generate_password(),
        "change-this-admin-password": generate_password(20),
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    target.write_text(content, encoding="utf-8")
    print(f"Wrote secure secrets to {target}")
    print("Run scripts/secure_mysql.ps1 to apply DB passwords to MySQL.")


if __name__ == "__main__":
    main()
