# AI-Powered CCTV Monitoring System

Production-style real-time CCTV monitoring with face detection, recognition, attendance logging, and a web dashboard.

**Repository:** [github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems](https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems)

## Session 10 Status (Complete)

Centralized error handling with file logging:

| Area | Behavior |
|------|----------|
| Camera disconnect | Status overlay on stream, auto-reconnect every 3s, logged to `logs/errors.log` |
| Database errors | Rollback + safe commits; dashboard falls back to empty stats |
| Missing face images | Skipped during embedding rebuild with warning in logs |
| All errors | Written to `logs/app.log` (INFO+) and `logs/errors.log` (ERROR+) |

```powershell
python scripts\verify_session10.py
```

## Session 9 Status (Complete)

Centralized configuration via `.env`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=cctv_user
DB_PASSWORD=your_password
DB_NAME=smart_cctv

CAMERA_SOURCE=dahua
DAHUA_USERNAME=admin
DAHUA_PASSWORD=your_dahua_password
DAHUA_HOST=192.168.100.135
DAHUA_PORT=554
```

Verify configuration & security:

```powershell
python scripts\verify_session9.py
python scripts\check_config_security.py
```

**Security:** credentials stay in `.env` only (gitignored). RTSP passwords are masked in UI and `/api/health`.

## Session 7 Status (Complete)

- Unknown face screenshots saved to `screenshots/unknown/`
- Screenshot path stored in `unknown_faces` table
- Gallery at `/dashboard/unknown-faces`

## Session 6 Status (Complete)

- Dashboard overview with live statistics
- Total registered users
- Today's detections & unknown detections
- Recent activity table
- Attendance statistics (today + all-time)

```powershell
python scripts\verify_session6_7.py
```

## Session 5 Status (Complete)

- Webcam support (device index `0`, `1`, …)
- RTSP IP CCTV support (`rtsp://...`)
- Live stream page with bounding boxes + confidence %
- Attendance logging (`attendance` table)
- Duplicate attendance prevention (`ATTENDANCE_INTERVAL` seconds)

```powershell
python scripts\verify_session5.py
```

Configure in `.env`:

```env
CAMERA_SOURCE=0
RTSP_URL=rtsp://admin:password@192.168.1.100:554/stream1
ATTENDANCE_INTERVAL=300
```

## Session 4 Status (Complete)

- Load all registered faces from database
- Generate embeddings with DeepFace (Facenet)
- Live camera recognition at `/dashboard/monitor`
- Matched name on screen; **Unknown** when no match
- Detection logging to database + screenshots
- Rebuild embeddings after new registration

```powershell
pip install -r requirements.txt
python scripts\build_embeddings.py
python scripts\verify_session4.py
```

Open **Monitor** after login: http://127.0.0.1:8000/dashboard/monitor

## Session 3 Status (Complete)

- Register new person (`/dashboard/register`)
- Upload face image (JPG, PNG, WEBP — max 5 MB)
- Image saved to `datasets/` folder
- Person record stored in `users` table
- Protected routes (admin session required)
- User list with photo thumbnails

```powershell
python scripts\verify_session3.py
```

## Session 2 Status (Complete)

- Admin login page (`/login`)
- Session-based authentication (signed cookie)
- Protected dashboard routes (`/dashboard`, `/dashboard/detections`, `/dashboard/users`)
- Bootstrap 5 UI with sidebar navigation
- Default admin seeded from `.env` on first startup

### Admin login

1. Ensure `.env` has `ADMIN_USERNAME` and `ADMIN_PASSWORD` (included in `generate_secrets.py`).
2. Start the app and open [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login).
3. Use credentials from `.env`, or create another admin:

```powershell
python scripts\create_admin.py
```

Verify authentication:

```powershell
python scripts\verify_session2.py
```

## Session 1 Status (Complete)

- Clean architecture folder structure
- FastAPI application skeleton
- SQLAlchemy ORM models (`users`, `detections`, `unknown_faces`)
- MySQL database (native or Docker Compose)
- SQLite fallback (optional)
- Health check API at `/api/health`
- Security hardening scripts

## Prerequisites

- Python 3.11+
- pip
- MySQL 8.x (native install or Docker Compose)

## Quick Start

### 1. Clone & setup

```powershell
git clone https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-System.git
cd AI-Powered-CCTV-Monitoring-System

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Secure configuration

```powershell
copy .env.example .env
python scripts\generate_secrets.py
.\scripts\secure_mysql.ps1
```

This generates strong `SECRET_KEY`, `MYSQL_ROOT_PASSWORD`, and `DB_PASSWORD` in `.env` (never committed).

### 3. Start MySQL

**Docker:**

```powershell
docker compose up -d
docker compose ps
```

**Native MySQL:** ensure service is running, then run `scripts\secure_mysql.ps1`.

### 4. Run application

```powershell
python main.py
```

Open: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

Verify database:

```powershell
python scripts\verify_session1.py
```

## Security

| Practice | Status |
|----------|--------|
| `.env` in `.gitignore` | Yes |
| Strong secrets via `generate_secrets.py` | Yes |
| MySQL root password set | Via `secure_mysql.ps1` |
| App binds to `127.0.0.1` by default | Yes |
| MySQL Docker port bound to localhost | Yes |
| `DEBUG=false` by default | Yes |

**Never commit `.env` or real passwords.** Use `.env.example` placeholders only.

## Project Structure

```
smart-cctv/
├── app/
│   ├── api/              # REST routes
│   ├── services/         # Business logic (Session 2+)
│   ├── models/           # SQLAlchemy ORM models
│   ├── database/         # DB connection & session
│   ├── face_recognition/ # Face processing (Session 2+)
│   ├── camera/           # Webcam / RTSP (Session 2+)
│   ├── templates/        # Jinja2 dashboard (Session 3)
│   ├── static/           # CSS, JS, assets
│   └── utils/            # Config & helpers
├── scripts/              # Setup & security helpers
├── datasets/             # Registered face images
├── logs/                 # Application logs
├── screenshots/          # Detection snapshots
├── docker-compose.yml    # MySQL 8.0 service
├── main.py               # Entry point
└── requirements.txt
```

## Database

Tables (`users`, `detections`, `unknown_faces`) are created automatically on first startup.

### SQLite fallback (optional)

```env
DB_DRIVER=sqlite
```

## Roadmap

| Session | Focus |
|---------|-------|
| **1** | Scaffold, FastAPI, SQLAlchemy, MySQL, health check |
| **2** | Admin auth, session login, protected dashboard |
| **3** | Face registration — upload image, save to datasets, store in DB |
| **4** | Face recognition — DeepFace embeddings, live match, Unknown label |
| **5** | CCTV monitoring — webcam/RTSP, attendance logging, dedup |

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 DzCodeProgrammer
