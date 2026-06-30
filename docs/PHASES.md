# System phases — Smart CCTV

## Phase 1 (current) — Application-driven processing

CCTV provides a **live video stream** (RTSP). Smart CCTV on the server:

1. **Pulls frames** from Dahua/webcam/RTSP
2. **Face detection** (YuNet/Haar) on each processed frame
3. **Face recognition** (DeepFace Facenet512) on a configurable interval
4. **Raises events in-app** when a face is recognized or unknown:
   - Log to `detections` / `attendance_logs` / `unknown_faces`
   - Save screenshots for detections (unknown face gallery)
   - Optional **WhatsApp via Fonnte** (third-party API)

```text
[Dahua RTSP] → [Smart CCTV server]
                    ├─ Detection + Recognition (OpenCV + DeepFace)
                    ├─ MySQL logs
                    ├─ screenshots/ (unknown & detections)
                    └─ Fonnte API → WhatsApp (optional)
```

### WhatsApp rules (Phase 1)

| Notification | Who receives | Required? |
|--------------|--------------|-----------|
| Unknown face | `WA_ADMIN_PHONES` | Fonnte + admin phones configured |
| Attendance masuk/pulang | **User's own number only** | User **opt-in** by saving WhatsApp on Register/Users |
| Entire Fonnte feature | — | `WA_NOTIFY_ENABLED=true` (global toggle) |

- Users **do not have to** provide a WhatsApp number.
- Attendance is **always logged** in the dashboard when recognized; WA is extra.
- Without a user phone, **no attendance WA** is sent (admin is not used as fallback for attendance).

### Attendance shift (WIB)

- **Masuk:** 07:00–16:59 — max 1 WA per user per window
- **Pulang:** 17:00–06:59 — max 1 WA per user per window

---

## Phase 2 (planned) — CCTV event-driven

Wait for **events from the IP camera/NVR** (motion, IVS, SDK callback) instead of continuous stream processing on the laptop.

```text
[Dahua event] → HTTP/SDK callback → [Smart CCTV server]
                                      ├─ On-demand frame or camera snapshot
                                      ├─ Recognition (if needed)
                                      └─ Log + optional WA
```

Goals:

- Lower CPU/heat on 8 GB laptops
- No need for full-time MJPEG stream processing
- Screenshots optional if the camera sends snapshots with the event

**Not implemented yet.** Phase 1 must be stable first (recognition accuracy, attendance, optional WA).

See **[docs/DAHUA_DSS_API_SUMMARY.md](DAHUA_DSS_API_SUMMARY.md)** for extracted notes from `dahua-cctv.pdf` (DSS V8.7 HTTP/MQ alarm & event APIs). Raw text: `docs/extracted/dahua-cctv-full.txt`.

---

## Phase 1 checklist (skripsi / demo)

Run automated checks: `python scripts/crosscheck.py`

Manual demo (once before presentation):

1. Register user **without** WhatsApp → register **with** phone → Users page shows badge
2. Model settings → **Rebuild embeddings** (or auto after register)
3. Monitor → Start → verify green (known) / red (unknown) / yellow (detecting) boxes
4. Attendance page → **Shift** (Masuk/Pulang) + time with **WIB**
5. Optional: Model settings → test WA (works with token even if `WA_NOTIFY_ENABLED=false`)
6. Optional: enable WA → user gets masuk/pulang (max 1 per shift) → admin gets unknown face

- [x] Register users (with or without WhatsApp)
- [x] Rebuild embeddings after bulk register
- [x] Live Monitor → Start → green/red/yellow boxes
- [x] Attendance page shows masuk/pulang logs (WIB time)
- [ ] Optional: Fonnte device connected, test message OK *(manual — needs Fonnte account)*
- [ ] Optional: user with phone gets masuk/pulang WA (max 2/day) *(manual)*
- [ ] Optional: admin gets unknown-face WA if enabled *(manual)*
