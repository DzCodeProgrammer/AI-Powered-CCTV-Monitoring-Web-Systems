# API Documentation

Base URL (development): `http://127.0.0.1:8000`

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI)

---

## Authentication

The dashboard uses **session cookies**. After a successful login, the browser stores a signed session cookie. Protected routes redirect to `/login` if unauthenticated.

| Cookie | Set by | Purpose |
|--------|--------|---------|
| `session` | `POST /login` | Signed admin session |

Session keys stored server-side:

- `admin_id`
- `admin_username`

Logout clears the session via `POST /logout`.

---

## Public API

### `GET /api/health`

Health check — no authentication required.

**Response `200`:**

```json
{
  "status": "ok",
  "app": "Smart CCTV Face Recognition",
  "environment": "development",
  "database": "ok",
  "db_driver": "mysql",
  "db_host": "localhost",
  "db_name": "smart_cctv",
  "camera_mode": "dahua",
  "camera_source": "rtsp://***:***@192.168.100.135:554/cam/realmonitor?channel=1&subtype=0",
  "performance": {
    "low_end_mode": true,
    "frame_skip": 2,
    "detection_frame_skip": 2,
    "recognition_interval": 2.0,
    "process_max_width": 640,
    "stream_max_width": 960,
    "jpeg_quality": 72,
    "max_faces_per_frame": 2
  }
}
```

| Field | Values |
|-------|--------|
| `status` | `ok` or `degraded` |
| `database` | `ok` or `error` |
| `camera_source` | Masked RTSP credentials |

---

## Authentication Routes

### `GET /login`

Render login form (HTML).

---

### `POST /login`

Submit admin credentials.

**Form fields:**

| Field | Type | Required |
|-------|------|----------|
| `username` | string | Yes |
| `password` | string | Yes |

**Success:** `303` redirect to `/dashboard`

**Failure:** `401` with error message on login page

---

### `POST /logout`

Clear session and redirect to `/login`.

**Success:** `303` redirect

---

## Dashboard Routes (HTML, auth required)

All dashboard routes require an active admin session. Unauthenticated requests redirect to `/login`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to `/dashboard` or `/login` |
| GET | `/dashboard` | Overview stats & recent activity |
| GET | `/dashboard/detections` | Last 50 detections |
| GET | `/dashboard/users` | Registered users list |
| GET | `/dashboard/attendance` | Attendance log (last 100) |
| GET | `/dashboard/unknown-faces` | Unknown face gallery |
| GET | `/dashboard/unknown-faces/{id}/image` | Serve unknown face crop |
| GET | `/dashboard/register` | Registration form |
| GET | `/dashboard/monitor` | Live monitor page |

### Query parameters

| Path | Parameter | Description |
|------|-----------|-------------|
| `/dashboard/users` | `registered=<id>` | Flash success after registration |
| `/dashboard/monitor` | `rebuilt=1` | Embeddings rebuilt confirmation |
| `/dashboard/monitor` | `camera=1` | Camera switched confirmation |
| `/dashboard/monitor` | `error=camera\|rtsp\|dahua` | Camera config error |
| `/dashboard` | `error=server` | Server error fallback |

---

## Registration Routes

### `POST /dashboard/register`

Register a new person with a face photo.

**Auth:** Required

**Multipart form:**

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | string | Max 100 chars, unique |
| `image` | file | JPG/PNG/WEBP, max 5 MB |

**Success:** `303` redirect to `/dashboard/users?registered=<id>`

**Errors:** `400` with validation message

Side effects:

1. Image saved to `datasets/`
2. Row inserted in `users`
3. Embedding cache rebuilt

---

### `GET /dashboard/datasets/{filename}`

Serve a registered face image from `datasets/`.

**Auth:** Required

**Success:** `200` image file

**Failure:** `303` redirect to `/dashboard/users`

---

## Monitoring Routes

### `GET /dashboard/monitor/feed`

MJPEG live stream with face bounding boxes.

**Auth:** Required

**Response:**

```
Content-Type: multipart/x-mixed-replace; boundary=frame
```

Each part is a JPEG frame with overlaid boxes:

- Green — recognized user + confidence %
- Red — unknown face
- Yellow — detecting (DeepFace pending)

Side effects (background): detection and attendance logging for recognized/unknown matches.

**Failure:** `503` if camera cannot initialize

---

### `POST /dashboard/monitor/camera`

Switch camera source for the session.

**Auth:** Required

**Form fields:**

| Field | Type | Description |
|-------|------|-------------|
| `camera_mode` | string | `webcam`, `dahua`, or `rtsp` |
| `webcam_index` | string | Device index when mode=webcam (default `0`) |
| `rtsp_url` | string | Full RTSP URL when mode=rtsp |

**Success:** `303` → `/dashboard/monitor?camera=1`

**Errors:** `303` → `/dashboard/monitor?error=<code>`

| Error code | Cause |
|------------|-------|
| `camera` | Could not open source |
| `rtsp` | Empty RTSP URL |
| `dahua` | `DAHUA_HOST` not configured |

Session keys set: `camera_mode`, `camera_source`, `rtsp_url`, `webcam_index`

---

### `POST /dashboard/monitor/rebuild-embeddings`

Rebuild face embedding cache from all active users in database.

**Auth:** Required

**Success:** `303` → `/dashboard/monitor?rebuilt=1`

---

## Error Responses

### Database unavailable

**`503`** JSON (API routes):

```json
{
  "detail": "Database temporarily unavailable. Please try again."
}
```

### Unauthenticated

**`303`** redirect to `/login` (HTML routes)

---

## Static Assets

| Path | Description |
|------|-------------|
| `/static/css/app.css` | Dashboard styles |
| `/static/js/*` | Client scripts |

---

## Environment Variables Affecting API

See `.env.example` for full list. Key variables:

```env
HOST=127.0.0.1
PORT=8000
SECRET_KEY=...
SESSION_MAX_AGE=86400
CAMERA_SOURCE=dahua
ATTENDANCE_INTERVAL=300
DETECTION_INTERVAL=1.0
```

---

## Example — Health Check with curl

```powershell
curl http://127.0.0.1:8000/api/health
```

```bash
curl -s http://127.0.0.1:8000/api/health | python -m json.tool
```

---

## Example — Login with curl

```powershell
curl -c cookies.txt -X POST http://127.0.0.1:8000/login `
  -d "username=admin&password=your_password" -L
```

Use `-b cookies.txt` for subsequent authenticated requests.

---

## Related Docs

- [Installation Guide](INSTALLATION.md)
- [Project Structure](PROJECT_STRUCTURE.md)
- [Database Setup](DATABASE.md)
- [Deployment Guide](DEPLOYMENT.md)
