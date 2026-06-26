# Deployment Guide

Deploy the Smart CCTV system for production use on a local network or server.

---

## Deployment Overview

```mermaid
flowchart LR
    subgraph internet [Network]
        Client[Admin Browser]
        Camera[IP CCTV / RTSP]
    end

    subgraph server [Application Server]
        Nginx[Nginx Reverse Proxy]
        Uvicorn[Uvicorn + FastAPI]
        App[Smart CCTV App]
    end

    subgraph data [Data Layer]
        MySQL[(MySQL 8)]
        Files[datasets / screenshots / logs]
    end

    Client -->|HTTPS :443| Nginx
    Nginx -->|HTTP :8000| Uvicorn
    Uvicorn --> App
    App --> MySQL
    App --> Files
    Camera -->|RTSP| App
```

---

## Pre-Deployment Checklist

- [ ] Strong secrets generated (`python scripts/generate_secrets.py`)
- [ ] `.env` never committed to git
- [ ] `DEBUG=false` in `.env`
- [ ] `HOST=0.0.0.0` only if server must accept remote connections
- [ ] MySQL not exposed to public internet
- [ ] Firewall allows only required ports (443, RTSP from camera subnet)
- [ ] HTTPS enabled via reverse proxy
- [ ] Admin password changed from default
- [ ] Log rotation configured (`logs/` grows over time)

---

## Production Environment Variables

```env
APP_ENV=production
DEBUG=false
HOST=127.0.0.1
PORT=8000
SECRET_KEY=<64-char-random>

DB_DRIVER=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=cctv_user
DB_PASSWORD=<strong-password>
DB_NAME=smart_cctv

CAMERA_SOURCE=dahua
DAHUA_HOST=192.168.100.135
DAHUA_USERNAME=admin
DAHUA_PASSWORD=<camera-password>

ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-admin-password>
SESSION_MAX_AGE=86400

LOW_END_MODE=true
FRAME_SKIP=2
RECOGNITION_INTERVAL=2.0
```

> Bind Uvicorn to `127.0.0.1` and put Nginx in front for public access. Do not expose port 8000 directly to the internet.

---

## Option 1 — Windows Server (Local Network)

### 1. Install dependencies

Follow [Installation Guide](INSTALLATION.md) through step 6.

### 2. Run as a background service

Use **NSSM** (Non-Sucking Service Manager):

```powershell
nssm install SmartCCTV "C:\path\to\venv\Scripts\python.exe" "C:\path\to\main.py"
nssm set SmartCCTV AppDirectory "C:\path\to\smart-cctv"
nssm set SmartCCTV AppEnvironmentExtra "APP_ENV=production"
nssm start SmartCCTV
```

### 3. Start MySQL via Docker

```powershell
docker compose up -d
```

Set Docker to restart on boot (Docker Desktop → Settings → General → Start on login).

### 4. Firewall

Allow inbound **only** from trusted admin subnets if exposing the web UI beyond localhost.

---

## Option 2 — Linux with systemd

### 1. Install system packages

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv nginx
```

### 2. Deploy application

```bash
git clone https://github.com/DzCodeProgrammer/AI-Powered-CCTV-Monitoring-Web-Systems.git
cd AI-Powered-CCTV-Monitoring-Web-Systems
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/generate_secrets.py
```

### 3. MySQL via Docker

```bash
docker compose up -d
```

### 4. Create systemd service

`/etc/systemd/system/smart-cctv.service`:

```ini
[Unit]
Description=Smart CCTV Face Recognition
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=cctv
WorkingDirectory=/opt/smart-cctv
Environment=APP_ENV=production
ExecStart=/opt/smart-cctv/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable smart-cctv
sudo systemctl start smart-cctv
sudo systemctl status smart-cctv
```

---

## Nginx Reverse Proxy

`/etc/nginx/sites-available/smart-cctv`:

```nginx
server {
    listen 443 ssl http2;
    server_name cctv.example.local;

    ssl_certificate     /etc/ssl/certs/cctv.crt;
    ssl_certificate_key /etc/ssl/private/cctv.key;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # MJPEG stream — disable buffering
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/smart-cctv /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

For local/LAN deployment with self-signed certificates:

```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/cctv.key \
  -out /etc/ssl/certs/cctv.crt
```

---

## Camera Network Requirements

| Requirement | Detail |
|-------------|--------|
| RTSP port | Default `554` — must be reachable from app server |
| Subnet | App server and camera on same VLAN recommended |
| Dahua URL | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0` |
| Bandwidth | ~2–4 Mbps per stream at 960p |

Test RTSP from server:

```bash
ffplay -rtsp_transport tcp "rtsp://admin:password@192.168.100.135:554/cam/realmonitor?channel=1&subtype=0"
```

---

## Performance Tuning (Production)

For **i5 Gen 4 / 8 GB RAM** servers:

```env
LOW_END_MODE=true
FRAME_SKIP=3
DETECTION_FRAME_SKIP=2
RECOGNITION_INTERVAL=2.5
PROCESS_MAX_WIDTH=640
STREAM_MAX_WIDTH=854
MAX_FACES_PER_FRAME=2
JPEG_QUALITY=70
```

Monitor CPU/RAM while stream runs. Increase `FRAME_SKIP` if CPU stays above 80%.

---

## Logging & Monitoring

| Log file | Contents |
|----------|----------|
| `logs/app.log` | General INFO+ events |
| `logs/errors.log` | ERROR+ only |

Rotate logs periodically or use `logrotate`:

```
/opt/smart-cctv/logs/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
```

Health monitoring:

```bash
curl -sf http://127.0.0.1:8000/api/health | jq .status
```

Alert if `status != "ok"` or `database != "ok"`.

---

## Backup Strategy

Daily backup script example:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
docker exec smart-cctv-mysql mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" smart_cctv \
  > /backup/smart_cctv_$DATE.sql
tar -czf /backup/smart_cctv_files_$DATE.tar.gz datasets/ screenshots/ database/embeddings.pkl
```

Store `.env` separately in a secrets manager — not in the tarball.

---

## Security Hardening

| Item | Action |
|------|--------|
| Secrets | Rotate `SECRET_KEY`, DB passwords quarterly |
| Admin | Use strong password; create separate admin per operator |
| Network | Isolate camera VLAN; no port forwarding for RTSP |
| HTTPS | Required for any remote admin access |
| MySQL | Bind to `127.0.0.1` only (default in docker-compose) |
| Updates | Keep Python packages and MySQL patched |

Run security check before go-live:

```powershell
python scripts\check_config_security.py
```

---

## Updating the Application

```bash
cd /opt/smart-cctv
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart smart-cctv
```

Verify after update:

```bash
curl http://127.0.0.1:8000/api/health
python scripts/verify_session1.py
```

---

## Troubleshooting Production

| Symptom | Check |
|---------|-------|
| 502 Bad Gateway | `systemctl status smart-cctv`; Uvicorn running? |
| Stream freezes | Nginx `proxy_buffering off`; camera RTSP stable? |
| High CPU | Increase `FRAME_SKIP`; reduce `STREAM_MAX_WIDTH` |
| DB errors | `docker compose ps`; `logs/errors.log` |
| Login fails | `ADMIN_PASSWORD` in `.env`; admin row in DB |

---

## Related Docs

- [Installation Guide](INSTALLATION.md)
- [Database Setup](DATABASE.md)
- [API Documentation](API.md)
