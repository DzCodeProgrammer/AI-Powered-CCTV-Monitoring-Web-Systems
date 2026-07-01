# Smart CCTV — Desktop Monitoring System

Real-time CCTV monitoring with **face detection**, **face recognition**, **attendance logging**, and admin dashboard — available as a **native desktop app** (recommended) or **web dashboard** (development / legacy).

**Repository:** [github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems](https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems)

---

## Desktop app (recommended — single admin laptop)

```powershell
pip install -r requirements.txt -r requirements-desktop.txt
copy .env.example .env
# Edit .env: MySQL, Dahua camera, admin password
python desktop_main.py
```

Or `run_desktop.bat` · See **[Desktop Guide](docs/DESKTOP.md)** · Build `.exe`: `scripts\build_desktop.bat`

**Desktop tabs:** Live Monitor · Attendance (+ Excel export) · Register · Unknown Faces · Model Settings · system tray (Start/Stop).

**Recommended `.env` for desktop laptop:**

```env
CCTV_MODE=event          # Dahua events in background; live monitor on-demand
RECOGNITION_INTERVAL=1   # Low-latency recognition
WA_NOTIFY_ENABLED=false  # Disable WhatsApp until Fonnte is configured
DESKTOP_MODE=true
```

---

## Features

- **Native desktop app** (PySide6) — register, model settings, unknown faces, Excel export, system tray
- Live stream — webcam, RTSP, or Dahua IP CCTV (+ event capture; default `event` mode on desktop)
- YuNet + Haar face detection with colored bounding boxes (thread-safe pipeline for stream + events)
- DeepFace (Facenet512) recognition + model settings UI
- Attendance logging with duplicate prevention
- **WhatsApp notifications** (Fonnte, optional) — disable via `WA_NOTIFY_ENABLED=false` or Model Settings tab
- **Export attendance to Excel** (`.xlsx`)
- Multi-photo registration, monitoring schedule
- Admin session authentication
- Optimized for i5 Gen 4 / 8 GB RAM (low-latency presets)
- Centralized `.env` configuration + file logging
- Single-instance desktop — prevents two DeepFace processes

---

## Quick Start

```powershell
git clone https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems.git
cd AI-Powered-CCTV-Monitoring-Web-Systems

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
python scripts\generate_secrets.py
docker compose up -d
python scripts\migrate_schema.py
python main.py
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/login | Admin login |
| http://127.0.0.1:8000/dashboard | Overview |
| http://127.0.0.1:8000/dashboard/model-settings | Model & training tuning |
| http://127.0.0.1:8000/dashboard/monitor | Live CCTV |
| http://127.0.0.1:8000/dashboard/attendance/export/preview | Export Excel |
| http://127.0.0.1:8000/api/health | Health check |
| http://127.0.0.1:8000/docs | Swagger UI |

### Run & host on LAN

```powershell
.\scripts\start_host.ps1
```

Opens the app on **all network interfaces** — use the **Network** URL printed in the console from phones or other PCs on the same Wi‑Fi.

See [Hosting Guide](docs/HOSTING.md) · double-click `run_host.bat`

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation Guide](docs/INSTALLATION.md) | Step-by-step setup |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Architecture & modules |
| [Database Setup](docs/DATABASE.md) | MySQL schema & migrations |
| [API Documentation](docs/API.md) | Routes & responses |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment |
| [Desktop Guide](docs/DESKTOP.md) | Native app & `.exe` build |
| [Operations Guide](docs/OPERATIONS.md) | Schedule, cleanup, auto-start |
| [Notifications Guide](docs/NOTIFICATIONS.md) | WhatsApp Fonnte + absensi shift |
| [Final Deliverables](docs/DELIVERABLES.md) | Session 15 checklist |

**SQL scripts:** [`scripts/init_mysql.sql`](scripts/init_mysql.sql) · [`scripts/schema.sql`](scripts/schema.sql)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Desktop | PySide6 (native UI) |
| Database | MySQL 8.x (SQLite fallback) |
| ORM | SQLAlchemy 2.x |
| Face AI | OpenCV YuNet/Haar, DeepFace Facenet |
| Export | openpyxl |
| Frontend | Jinja2, Bootstrap 5 (web mode) |

---

## Target Hardware

Intel Core i5 Gen 4 · 8 GB RAM · 128 GB SSD · `LOW_END_MODE=true` (default)

### Operations (schedule, cleanup, auto-start)

See **[docs/OPERATIONS.md](docs/OPERATIONS.md)** for:

- **Monitoring schedule** — auto start/stop e.g. 07:00–17:00 (saves CPU/heat)
- **Disk cleanup** — old `logs/` and `screenshots/` on a timer (HDD-friendly)
- **Windows auto-start** — `.\scripts\install_autostart.ps1`

Tune these from **Dashboard → Model settings → Operations** or `.env`.

### WhatsApp (optional)

Disabled by default (`WA_NOTIFY_ENABLED=false`). Enable in **Desktop → Model Settings → WhatsApp** or web **Model settings**, after setting `WA_API_TOKEN` and `WA_ADMIN_PHONES` in `.env`. See **[docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md)**.

### Camera stream

Use **DAHUA_SUBTYPE=1** substream on low-end laptops. For local testing without CCTV, pick **Webcam** in Live Monitor.

### Desktop app closes during monitoring?

Usually caused by OpenCV YuNet + Dahua events running at the same time (fixed with AI pipeline lock). If issues persist, set `FACE_DETECTOR=haar` in `.env` and restart. Check `logs/errors.log`.

---

## Verification (Sessions 1–15)

```powershell
python scripts\verify_session13.py   # Code quality
python scripts\verify_session14.py   # Excel export
python scripts\verify_session15.py   # Final deliverables
python scripts\check_config_security.py
```

---

## Project Structure

```
smart-cctv/
├── app/                 # Application source (api, services, models, …)
├── scripts/             # SQL, verify, setup utilities
├── docs/                # Full documentation
├── database/            # Embeddings cache (+ SQLite if used)
├── datasets/            # Registered face photos
├── logs/                # app.log, errors.log
├── main.py              # Web entry point
├── desktop_main.py      # Desktop entry point (recommended)
├── requirements.txt     # Pinned dependencies
├── pyproject.toml       # Ruff / PEP8 config
└── docker-compose.yml   # MySQL 8.0
```

---

## Security

- `.env` is gitignored — run `python scripts\generate_secrets.py`
- RTSP passwords masked in UI and `/api/health`
- Default bind: `127.0.0.1` (use Nginx for production)

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 DzCodeProgrammer
