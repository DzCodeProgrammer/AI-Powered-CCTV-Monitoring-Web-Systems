"""Extract text from dahua-cctv.pdf; search event/alarm/HTTP topics."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "dahua-cctv.pdf"
OUT_DIR = ROOT / "docs" / "extracted"
OUT_FULL = OUT_DIR / "dahua-cctv-full.txt"
OUT_INDEX = OUT_DIR / "dahua-cctv-keywords.txt"

KEYWORDS = re.compile(
    r"event|alarm|subscribe|subscription|callback|notification|http|cgi|"
    r"snapshot|capture|listen|ivs|motion|face|rtsp|onvif|netsdk|sdk|"
    r"push|webhook|picture|jpeg|multipart",
    re.IGNORECASE,
)


def main() -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("Installing pypdf...", file=sys.stderr)
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "-q"])
        from pypdf import PdfReader

    if not PDF.is_file():
        print(f"PDF not found: {PDF}", file=sys.stderr)
        return 1

    reader = PdfReader(str(PDF))
    total = len(reader.pages)
    print(f"Pages: {total}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keyword_hits: list[str] = []

    with OUT_FULL.open("w", encoding="utf-8", errors="replace") as full:
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            full.write(f"\n{'=' * 60}\nPAGE {i}\n{'=' * 60}\n{text}\n")
            if KEYWORDS.search(text):
                snippet = text[:2000].replace("\n", " ")
                keyword_hits.append(f"--- PAGE {i} ---\n{text}\n")

    OUT_INDEX.write_text("\n".join(keyword_hits), encoding="utf-8", errors="replace")
    print(f"Wrote {OUT_FULL} ({OUT_FULL.stat().st_size // 1024} KB)")
    print(f"Wrote {OUT_INDEX} ({len(keyword_hits)} pages with keywords)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
