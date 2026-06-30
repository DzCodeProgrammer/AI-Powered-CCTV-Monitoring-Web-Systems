# Dahua DSS V8.7 API — Ringkasan Ekstraksi

Sumber: `dahua-cctv.pdf` (622 halaman)  
Judul: **Dahua DSS Platform API Document** — `Dahua-HTTP-API-For-DSS-V8.7_EN`  
Teks penuh: `docs/extracted/dahua-cctv-full.txt` (~984 KB)  
Halaman relevan keyword: `docs/extracted/dahua-cctv-keywords.txt` (~913 KB)

Script ekstraksi: `scripts/extract_dahua_pdf.py` (butuh `pypdf`)

---

## Penting: DSS vs kamera IPC langsung

| | Setup Anda sekarang (Fase 1) | Dokumen PDF ini |
|---|------------------------------|-----------------|
| Target | Kamera IP Dahua langsung (`192.168.x.x`) | **Platform DSS/VMS** (server manajemen video) |
| Protokol | RTSP pull saja | HTTP REST + ActiveMQ + RTSP/FLV/HLS |
| Event push | Tidak ada | HTTP callback **atau** subscribe MQ |
| Login | User/password di URL RTSP | Http Digest 2-step + `X-Subject-Token` |

PDF ini **bukan** manual CGI kamera standalone (`/cgi-bin/snapshot.cgi`).  
Cocok jika kamera/NVR Anda **terdaftar di server Dahua DSS** dan integrasi lewat platform.

Untuk kamera IPC tanpa DSS, Fase 2 perlu **Dahua Device HTTP API** terpisah (bukan file ini).

---

## Arsitektur platform (DSS V8.7)

Modul inti VMS:

- Monitoring Center
- **Event Center** ← event & alarm
- Intelligent Search
- Access Control
- Face recognition
- Attendance, Vehicle, dll.

Integrasi pihak ketiga:

```text
[Developer App] ←HTTP REST→ [DSS VMS Server] ←→ [IPC/NVR devices]
       ↑                              │
       └──── ActiveMQ (real-time) ────┘
       └──── HTTP callback (alarm push) ────┘
```

Video: RTSP, FLV, HLS (via API `StartVideo`).

---

## Dua cara terima event / alarm

### 1. HTTP callback (disarankan di dokumen — lebih mudah)

**Subscribe:** `POST /brms/api/v1.1/push-data/alarm/subscribe`

```json
{
  "callbackUrl": "https://YOUR-SERVER/api/dahua/alarm",
  "action": "1",
  "signature": "random-string-for-auth"
}
```

- `action`: `1` = subscribe, `0` = unsubscribe
- Satu user hanya satu subscription; subscribe ulang **overwrite** yang lama
- User subscriber harus cocok dengan **notified subscriber** di alarm scheme VMS

**Callback format** (DSS POST ke `callbackUrl`):

| Field | Keterangan |
|-------|------------|
| `callbackType` | `1` = isi alarm utama; `2` = gambar linkage async |
| `alarmCode` | ID alarm |
| `sourceCode` / `sourceName` | Sumber alarm (channel/device) |
| `alarmType` / `alarmTypeName` | Jenis alarm (lihat dict 6.1.7) |
| `alarmGrade` | 1=High, 2=Medium, 3=Low |
| `alarmStatus` | 1=generated, 2=cleared |
| `alarmTime` | Timestamp |
| `alarmPictures` | Array gambar **Base64** (opsional) |
| `extData` | JSON extended (face recognition, dll.) |

**Catatan gambar:**  
- `callbackType=2`: hanya update `alarmPictures` (increment), jangan overwrite field lain  
- Bisa ada **2 callback** per alarm (body + linkage image)

### 2. ActiveMQ (real-time)

Subscribe topic (setelah login, dapat `userId` / `userGroupId`):

| Topic | Contoh |
|-------|--------|
| Alarm | `mq.alarm.msg.topic.{userId}` |
| Alarm (group) | `mq.alarm.msg.group.topic.{userGroupId}` |
| Event | `mq.event.msg.topic.{userId}` |
| Public | `mq.common.msg.topic` |

Format pesan JSON:

```json
{
  "id": "112456",
  "method": "brms.notifyAlarms",
  "info": [ { "...": "..." } ]
}
```

**MQ alarm** (`brms.notifyAlarms`) menyertakan antara lain:

- `alarmPicture` — URL snapshot alarm
- `faceRecognitionInfo` — `personId`, `personName`, `similarity`, `captureFaceImageUrl`
- `linkVideoChannels`, `linkRecordChannels` — linkage video

---

## API komunikasi video & snapshot

### Live stream (RTSP via platform)

`POST /brms/api/v1.0/MTS/Video/StartVideo`

Body: `channelId`, `streamType` (1=main, 2=sub), `dataType`, dll.

Return: `url` (RTSP) + `token` → pakai sebagai `url?token=xxx`

### Capture gambar on-demand (baru V11 — 2025.07.30)

`POST /brms/api/v1.1/device/channel/{channelId}/video/capture`

- Ambil **1 frame** dari live video channel
- **Jangan** dipanggil terlalu sering (rate limit)
- Return: `fileUrl` (download dengan `?token={credential}`)

### Query alarm historis

`POST /eams/api/v1.1/alarm/record/fetch/page`

Filter: waktu, device, channel, tipe alarm, status handle, dll.  
Return termasuk `picture` (snapshot alarm).

### Face terkait alarm

- Get alarm related **face snapshot**
- Get alarm related **face recognition** info  
  (person name, similarity, capture URL — lihat §3.6 di teks penuh)

---

## Alur integrasi tipikal (§5.10.4)

1. Di VMS client: **Add Device** (kamera yang bisa trigger alarm)
2. **Alarm scheme**: Applications Config → Event → tipe, sumber, linkage, user penerima
3. **Login API**: Http Digest 2-step → simpan token → header `X-Subject-Token`
4. Pilih **MQ** atau **HTTP callback** untuk terima alarm
5. `POST .../alarm/subscribe` dengan `callbackUrl` server Anda
6. Device trigger alarm → DSS push ke callback / MQ

---

## Modul API lain (daftar isi)

| § | Modul | Relevansi Smart CCTV |
|---|--------|----------------------|
| 3.4 | Live View | RTSP stream on-demand |
| 3.5 | Record Playback | Playback rekaman |
| 3.6 | **Alarm (Event Center)** | **Inti Fase 2** |
| 3.8 | Person | Database person platform |
| 3.10 | Attendance | Absensi platform (bisa beda dengan app Anda) |
| 3.12 | **Face** | Face library / recognition di DSS |
| 4.2 | MQ Alarm | Real-time push |
| 5.10 | Alarm Messages (best practice) | Panduan subscribe |

Appendix **6.1.7 Alarm Type** — daftar kode alarm (motion, IVS, face, access control, dll.) — lihat halaman ~552+ di teks ekstrak.

---

## Pemetaan ke Smart CCTV Phase 2

```text
[DSS alarm: motion/face/IVS]
        │
        ▼ HTTP POST callback  ATAU  ActiveMQ brms.notifyAlarms
[Smart CCTV FastAPI]
        ├─ Parse alarmType, channelId, alarmPictures (Base64/URL)
        ├─ Jika perlu: POST .../video/capture  atau download alarmPicture
        ├─ Face recognition (DeepFace) jika DSS belum kirim personName
        ├─ log_attendance + MySQL
        └─ WA Fonnte (opsional)
```

**Tanpa stream MJPEG 24/7** — proses hanya saat event.

### Prasyarat infrastruktur

- Server **Dahua DSS V8.7** running
- Kamera IPC Anda **added** ke DSS (bukan hanya RTSP langsung ke laptop)
- Smart CCTV bisa diakses DSS (LAN/public + firewall) untuk `callbackUrl`
- Atau consumer ActiveMQ jika pakai MQ

### Jika tetap kamera langsung (tanpa DSS)

Opsi alternatif (di luar PDF ini):

- Dahua device HTTP: motion event / snapshot CGI
- ONVIF events
- Tetap RTSP + polling ringan (mirip Fase 1, interval besar)

---

## Autentikasi HTTP (ringkas)

1. `POST /brms/api/v1.0/accounts/authorize` → 401 + realm/randomKey
2. Login kedua dengan digest → `token`, `credential`, `userId`
3. Semua API: header `X-Subject-Token: {token}`
4. Download gambar: `Url?token={credential}`

URL pola: `https://{host}:{port}/{subsystem}/api/{version}/{module}/...`

---

## File ekstrak

Jalankan ulang:

```bat
run_extract_pdf.bat
```

atau:

```powershell
venv\Scripts\python.exe scripts\extract_dahua_pdf.py
```

(Gunakan `subst Z:` jika path `GAL'EN` error di shell.)
