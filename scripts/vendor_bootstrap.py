"""Download Bootstrap + Bootstrap Icons into app/static/vendor for offline use."""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "app" / "static" / "vendor"
FONTS = VENDOR / "fonts"

FILES = {
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css": VENDOR / "bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js": VENDOR / "bootstrap.bundle.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css": VENDOR / "bootstrap-icons.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2": FONTS / "bootstrap-icons.woff2",
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff": FONTS / "bootstrap-icons.woff",
}


def main() -> None:
    VENDOR.mkdir(parents=True, exist_ok=True)
    FONTS.mkdir(parents=True, exist_ok=True)
    for url, dest in FILES.items():
        print(f"Fetching {dest.name}...")
        urllib.request.urlretrieve(url, dest)
    css = (VENDOR / "bootstrap-icons.min.css").read_text(encoding="utf-8")
    css = css.replace('url("./fonts/', 'url("/static/vendor/fonts/')
    css = css.replace("url(\"./fonts/", "url(\"/static/vendor/fonts/")
    (VENDOR / "bootstrap-icons.min.css").write_text(css, encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
