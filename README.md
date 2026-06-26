# AI-Powered CCTV Monitoring Web System

Real-time CCTV monitoring with **face detection**, **face recognition**, **attendance logging**, and a **web dashboard**. Built with Python, FastAPI, OpenCV, DeepFace, and MySQL.

**Repository:** [github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems](https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems)

---

## Features

- Live MJPEG stream from **webcam**, **RTSP**, or **Dahua IP CCTV**
- Colored face bounding boxes (green = recognized, red = unknown, yellow = detecting)
- Register persons with face photos; automatic embedding rebuild
- Attendance logging with duplicate prevention
- Unknown face gallery with cropped screenshots
- Admin session authentication
- Optimized for low-end hardware (i5 Gen 4 / 8GB RAM)
- Centralized `.env` configuration and file-based error logging

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
python main.py
```

Open [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login) and sign in with credentials from `.env`.

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation Guide](docs/INSTALLATION.md) | Step-by-step setup on Windows |
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Folder layout and architecture |
| [Database Setup](docs/DATABASE.md) | MySQL, SQLite, tables, and migrations |
| [API Documentation](docs/API.md) | Routes, auth, and response formats |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment with Nginx and systemd |

Interactive API explorer (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | MySQL 8.x (SQLite fallback) |
| ORM | SQLAlchemy 2.x |
| Face AI | OpenCV (Haar), DeepFace (Facenet) |
| Frontend | Jinja2, Bootstrap 5 |
| Auth | Session cookies (Starlette SessionMiddleware) |

---

## Target Hardware

| Component | Minimum |
|-----------|---------|
| CPU | Intel Core i5 Gen 4 (or equivalent) |
| RAM | 8 GB |
| Storage | 128 GB SSD |
| OS | Windows 10/11 or Linux |

Enable `LOW_END_MODE=true` in `.env` (default) for best performance on this profile.

---

## Verification Scripts

```powershell
python scripts\verify_session1.py    # Database & health
python scripts\verify_session2.py    # Authentication
python scripts\verify_session9.py  # Configuration
python scripts\verify_session10.py # Error handling
python scripts\verify_session11.py # Performance
python scripts\verify_session12.py # Documentation
python scripts\check_config_security.py
```

---

## Security

- `.env` is gitignored — never commit secrets
- Run `python scripts\generate_secrets.py` for strong passwords
- RTSP credentials are masked in UI and `/api/health`
- App binds to `127.0.0.1` by default in development

See [Deployment Guide](docs/DEPLOYMENT.md) for HTTPS and production hardening.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 DzCodeProgrammer
