# Installation Guide

Step-by-step installation for **Windows 10/11**. Linux steps are noted where they differ.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| pip | Latest | Included with Python |
| Git | Any | To clone the repository |
| MySQL | 8.x | Docker Compose **or** native install |
| Docker Desktop | Optional | Easiest MySQL setup on Windows |

**Hardware:** Intel Core i5 Gen 4, 8 GB RAM, 128 GB SSD (minimum tested profile).

---

## 1. Clone the Repository

```powershell
git clone https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems.git
cd AI-Powered-CCTV-Monitoring-Web-Systems
```

---

## 2. Create a Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

**Linux/macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** TensorFlow and DeepFace are large packages (~2 GB). First install may take 5–10 minutes on a slow connection.

Verify imports:

```powershell
python -c "import fastapi, cv2, deepface; print('OK')"
```

---

## 4. Configure Environment

```powershell
copy .env.example .env
python scripts\generate_secrets.py
```

This writes secure values for:

- `SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `DB_PASSWORD`
- `DAHUA_PASSWORD` (placeholder)
- `ADMIN_PASSWORD`

Edit `.env` manually for camera settings:

```env
CAMERA_SOURCE=dahua
DAHUA_USERNAME=admin
DAHUA_PASSWORD=your_camera_password
DAHUA_HOST=192.168.100.135
DAHUA_PORT=554
```

For a local webcam instead:

```env
CAMERA_SOURCE=0
```

---

## 5. Start MySQL

### Option A — Docker Compose (recommended)

```powershell
docker compose up -d
docker compose ps
```

Wait until the `mysql` service shows **healthy**.

### Option B — Native MySQL 8.x

1. Install MySQL Server 8.x from [dev.mysql.com](https://dev.mysql.com/downloads/mysql/).
2. Start the MySQL service.
3. Apply credentials:

```powershell
.\scripts\secure_mysql.ps1
```

See [Database Setup Guide](DATABASE.md) for manual SQL steps.

---

## 6. Run the Application

```powershell
python main.py
```

Expected output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open in browser:

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/login | Admin login |
| http://127.0.0.1:8000/dashboard | Dashboard overview |
| http://127.0.0.1:8000/dashboard/monitor | Live CCTV stream |
| http://127.0.0.1:8000/api/health | Health check JSON |
| http://127.0.0.1:8000/docs | Swagger UI |

**Default admin credentials** are in `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<generated>
```

---

## 7. Register Faces & Start Monitoring

1. Log in at `/login`.
2. Go to **Register** → upload a face photo and enter a name.
3. Open **Live Monitor** → select camera source (Webcam / Dahua / RTSP).
4. Click **Rebuild embeddings** if recognition does not start immediately.

Build embeddings manually:

```powershell
python scripts\build_embeddings.py
```

---

## 8. Verify Installation

Run verification scripts in order:

```powershell
python scripts\verify_session1.py
python scripts\verify_session2.py
python scripts\verify_session9.py
python scripts\check_config_security.py
```

All should print `OK` and exit with code `0`.

---

## Troubleshooting

### MySQL connection refused

- Ensure Docker container is running: `docker compose ps`
- Check `.env` values: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`
- Run `python scripts\verify_session1.py`

### Camera not opening

- Webcam: try `CAMERA_SOURCE=0` or `1`
- Dahua: verify PC is on same network as camera IP
- Check `logs/errors.log` for RTSP errors

### DeepFace / TensorFlow slow on first run

- First inference downloads model weights (~100 MB) to `~/.deepface/`
- Subsequent runs are faster

### Port 8000 already in use

Change in `.env`:

```env
PORT=8080
```

---

## Next Steps

- [Project Structure](PROJECT_STRUCTURE.md)
- [Database Setup](DATABASE.md)
- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)
