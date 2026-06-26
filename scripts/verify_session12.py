"""Verify Session 12: documentation completeness."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = {
    "README.md": [
        "Quick Start",
        "Documentation",
        "Installation Guide",
        "API Documentation",
        "Deployment Guide",
    ],
    "docs/INSTALLATION.md": [
        "Prerequisites",
        "Clone",
        "Virtual Environment",
        "MySQL",
        "Troubleshooting",
    ],
    "docs/PROJECT_STRUCTURE.md": [
        "Directory Tree",
        "Architecture",
        "Request Flow",
    ],
    "docs/DATABASE.md": [
        "Schema",
        "users",
        "attendance_logs",
        "Docker Compose",
        "SQLite",
    ],
    "docs/API.md": [
        "/api/health",
        "Authentication",
        "/dashboard/monitor/feed",
        "POST /login",
    ],
    "docs/DEPLOYMENT.md": [
        "Nginx",
        "systemd",
        "Production",
        "Security",
    ],
}


def main() -> int:
    missing_files: list[str] = []
    missing_sections: list[str] = []

    for rel_path, keywords in REQUIRED_DOCS.items():
        path = PROJECT_ROOT / rel_path
        if not path.is_file():
            missing_files.append(rel_path)
            continue

        content = path.read_text(encoding="utf-8")
        for keyword in keywords:
            if keyword.lower() not in content.lower():
                missing_sections.append(f"{rel_path}: missing '{keyword}'")

    if missing_files:
        print("FAIL: missing documentation files:")
        for f in missing_files:
            print(f"  - {f}")
        return 1

    if missing_sections:
        print("FAIL: incomplete documentation sections:")
        for s in missing_sections:
            print(f"  - {s}")
        return 1

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    doc_links = [
        "docs/INSTALLATION.md",
        "docs/PROJECT_STRUCTURE.md",
        "docs/DATABASE.md",
        "docs/API.md",
        "docs/DEPLOYMENT.md",
    ]
    for link in doc_links:
        if link not in readme:
            print(f"FAIL: README.md missing link to {link}")
            return 1

    print(f"Documentation files: {len(REQUIRED_DOCS)} OK")
    for rel_path in REQUIRED_DOCS:
        lines = len((PROJECT_ROOT / rel_path).read_text(encoding="utf-8").splitlines())
        print(f"  {rel_path} ({lines} lines)")
    print("Session 12 documentation verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
