# FotoFindr

> **AI that understands your camera roll**

FotoFindr is an AI-powered mobile app that indexes your camera roll and makes it searchable with plain English. Upload your photos, let the pipeline tag them with object detection and emotion analysis, then search naturally — "photos where I look happy with my dog" — and get results instantly.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
  - [Backend](#backend-setup)
  - [Mobile](#mobile-setup)
- [API Reference](#api-reference)
  - [Health](#get-health)
  - [Upload](#post-upload)
  - [Reprocess](#post-reprocessuser_id)
  - [Pipeline Status](#get-statususer_id)
  - [Search](#post-search)
  - [Narrate](#post-narrate)
  - [Image Labels](#get-image_labels)
  - [Untagged Photos](#get-untaggeruser_id)
  - [All Photos](#get-photosuser_id)
  - [People Profiles](#get-profilesuser_id)
  - [Name a Person](#patch-profilesperson_idname)
  - [Clear Data](#post-clearuser_id)
- [How Search Works](#how-search-works)
- [How Narration Works](#how-narration-works)
- [Pipeline Flow](#pipeline-flow)
- [Database Schema](#database-schema)
- [Known Limitations](#known-limitations)

---

## Architecture

```
iPhone / Android
     │
     │  Expo React Native (TypeScript)
     │  - Uploads photos from MediaLibrary (batched, 3 at a time)
     │  - Natural language search bar
     │  - Photo modal with label chips + narration playback
     │  - Cleanup tab (untagged photos, delete from device)
     │
     ▼
FastAPI Backend  (Python, uvicorn, port 8080)
     │
     ├── SQLite  fotofindr.db              ← primary metadata store
     │   tables: photos, people
     │
     ├── /uploads/                         ← JPEG files, served as static
     ├── /uploads/narrations/              ← MP3 files from ElevenLabs
     │
     ├── YOLO  (ultralytics)               ← object detection
     ├── DeepFace                          ← emotion detection per face
     ├── Gemini 2.0 Flash  (text)          ← search label matching
     ├── Gemini 2.0 Flash  (vision)        ← photo description for narration
     └── ElevenLabs                        ← text-to-speech
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile | Expo React Native + TypeScript |
| Backend | Python 3.11 + FastAPI + uvicorn |
| Object Detection | YOLO via ultralytics |
| Emotion Detection | DeepFace |
| AI Search | Google Gemini 2.0 Flash (text) |
| AI Narration | Google Gemini 2.0 Flash (vision) + ElevenLabs TTS |
| Database | SQLite (primary) + Snowflake (optional mirror) |
| Image Storage | Local disk — `/uploads/` |
| Audio Storage | Local disk — `/uploads/narrations/` |

---

## Setup

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Create `backend/.env`:

```env
GEMINI_API_KEY=AIza...
ELEVENLABS_API_KEY=sk_...

# Optional — Snowflake metadata mirror (not required for search)
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_DATABASE=FOTOFINDR
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
```

> The server must be HTTP (not HTTPS) when developing locally. The mobile app connects over the local network.

### Mobile Setup

```bash
cd mobile
npm install --legacy-peer-deps
npx expo start
```

Create `mobile/.env`:

```env
EXPO_PUBLIC_API_URL=http://<YOUR_LOCAL_IP>:8080
```

Find your local IP with `ipconfig` (Windows) or `ifconfig` (Mac/Linux). The phone and the backend machine must be on the same network.

---

## API Reference

Base URL: `http://<host>:8080`

All endpoints return JSON. Errors follow:

```json
{ "detail": "Error message here" }
```

---

### GET /health

Liveness check.

**Response**
```json
{ "status": "ok" }
```

---

### POST /upload/

Upload a single photo. Accepts `multipart/form-data`. The image is converted to JPEG, resized to max 1080px wide, EXIF orientation corrected, and saved to `/uploads/{photo_id}.jpg`. HEIC/HEIF files from iPhones are supported.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | binary | yes | Image file (JPEG, PNG, HEIC, HEIF) |
| `user_id` | string | yes | User identifier (UUID) |
| `device_uri` | string | no | Device-side URI (`ph://ASSET_ID` on iOS). Used for device deletion in the cleanup tab. |

**Example (curl)**
```bash
curl -X POST http://localhost:8080/upload/ \
  -F "file=@photo.jpg" \
  -F "user_id=00000000-0000-0000-0000-000000000001" \
  -F "device_uri=ph://CC95F08C-88C3-4012-9D6D-64A413D254B3/L0/001"
```

**Response** `200`
```json
{
  "photo_id": "3f2a1b4c-...",
  "storage_url": "/uploads/3f2a1b4c-....jpg",
  "message": "Uploaded."
}
```

**Error codes**
| Code | Reason |
|---|---|
| 413 | File exceeds 20 MB |
| 415 | Not an image file |
| 400 | Image processing failed (corrupt file, etc.) |

> After uploading, call `/reprocess/{user_id}` to run YOLO and DeepFace on all uploaded photos.

---

### POST /reprocess/{user_id}

Queues the YOLO object detection and DeepFace emotion pipeline on all photos stored for `user_id`. Runs as FastAPI `BackgroundTasks` — returns immediately while processing continues in the background.

**Path parameters**

| Param | Description |
|---|---|
| `user_id` | User identifier |

**Example (curl)**
```bash
curl -X POST http://localhost:8080/reprocess/00000000-0000-0000-0000-000000000001
```

**Response** `200`
```json
{
  "queued": 28,
  "total": 30
}
```

- `queued` — number of photos whose image files were found on disk and queued
- `total` — total photos in SQLite for this user

Poll `/status/{user_id}` to track progress.

---

### GET /status/{user_id}

Returns pipeline processing progress for `user_id`.

**Example (curl)**
```bash
curl http://localhost:8080/status/00000000-0000-0000-0000-000000000001
```

**Response** `200`
```json
{
  "processed": 22,
  "total": 30
}
```

- `processed` — photos where `detected_objects` is not null (pipeline has run)
- `total` — all photos for the user

The mobile app polls this every 3 seconds and shows a progress bar. When `processed >= total` the app transitions to "Ready to Search".

---

### POST /search/

Natural language photo search. Uses Gemini to map the query to matching object/emotion labels, then filters photos in SQLite.

**Request body** `application/json`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | yes | — | Plain English search query |
| `user_id` | string | yes | — | User identifier |
| `limit` | integer | no | 20 | Max photos to return |

**Example (curl)**
```bash
curl -X POST http://localhost:8080/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "happy dog photos", "user_id": "00000000-0000-0000-0000-000000000001"}'
```

**Response** `200`
```json
{
  "ok": true,
  "photos": [
    {
      "id": "3f2a1b4c-...",
      "user_id": "00000000-0000-0000-0000-000000000001",
      "storage_url": "/uploads/3f2a1b4c-....jpg",
      "device_uri": "ph://CC95F08C-...",
      "detected_objects": [
        { "label": "dog", "confidence": 0.91 },
        { "label": "person", "confidence": 0.87 }
      ],
      "emotions": [
        { "dominant_emotion": "happy", "emotion": { "happy": 0.92, "neutral": 0.06 } }
      ],
      "importance_score": 1.0,
      "created_at": "2026-02-28T14:32:00"
    }
  ],
  "matched_labels": ["dog", "happy"]
}
```

If Gemini returns no matching labels (quota exceeded or unrecognizable query), `photos` contains all photos for the user up to `limit`.

**How it works:**

1. Load all photos for `user_id` from SQLite
2. Collect unique YOLO object labels and DeepFace emotion labels across all photos
3. Send `query + labels + emotions` to Gemini: *"Which of these labels match this query?"*
4. Gemini returns a subset of matching labels
5. Filter: keep photos that have at least one matching object label or emotion
6. Return filtered photos

Gemini cost: **1 text request per search call**.

---

### POST /narrate/

Generate an AI voice narration for a photo. Gemini Vision describes the image; ElevenLabs converts the description to speech. The MP3 is saved to disk and a URL is returned.

**Request body** — `multipart/form-data` (form fields)

| Field | Type | Required | Description |
|---|---|---|---|
| `photo_id` | string | yes | UUID of the photo (from `/upload/` response) |
| `user_id` | string | yes | User identifier |

**Example (curl)**
```bash
curl -X POST http://localhost:8080/narrate/ \
  -F "photo_id=3f2a1b4c-..." \
  -F "user_id=00000000-0000-0000-0000-000000000001"
```

**Response** `200`
```json
{
  "description": "A smiling woman and her golden retriever sitting in a sunny park.",
  "audio_url": "/uploads/narrations/3f2a1b4c-..._narrate.mp3"
}
```

The `audio_url` is a path served as a static file. Prefix with the server base URL to play it:
```
http://<host>:8080/uploads/narrations/3f2a1b4c-..._narrate.mp3
```

**Error codes**
| Code | Reason |
|---|---|
| 404 | `photo_id` not in database, or image file missing from disk |
| 502 | ElevenLabs API rejected the request (invalid key, quota exceeded) |
| 500 | Unexpected server error |

**How it works:**

1. Look up the photo in SQLite → get `detected_objects` and `emotions`
2. Read JPEG bytes from `/uploads/{photo_id}.jpg`
3. Call Gemini Vision with the image bytes + label hints → natural language description
4. If Gemini quota exceeded, fall back to a label-based description: *"A photo from your camera roll."*
5. POST the description text to ElevenLabs TTS API → MP3 bytes
6. Save MP3 to `/uploads/narrations/{photo_id}_narrate.mp3`
7. Return `{ description, audio_url }`

Gemini cost: **1 vision request per narrate call**.

---

### GET /image_labels/

Returns the detected object and emotion labels for a single photo.

**Query parameters**

| Param | Type | Required | Description |
|---|---|---|---|
| `image_id` | string | yes | Photo UUID |

**Example (curl)**
```bash
curl "http://localhost:8080/image_labels/?image_id=3f2a1b4c-..."
```

**Response** `200`
```json
{
  "image_id": "3f2a1b4c-...",
  "labels": ["dog", "person", "happy"]
}
```

Labels are a flat list combining YOLO object labels and DeepFace dominant emotions.

**Error codes**
| Code | Reason |
|---|---|
| 404 | `image_id` not found in database |

---

### GET /untagged/{user_id}

Returns photos that completed the AI pipeline but have no detected objects and no detected emotions — photos with zero content (blank shots, solid colors, duplicate screenshots, etc.).

> Only returns photos where the pipeline has already run (i.e., `detected_objects` is not null). Call `/reprocess/{user_id}` first.

**Example (curl)**
```bash
curl http://localhost:8080/untagged/00000000-0000-0000-0000-000000000001
```

**Response** `200`
```json
{
  "photos": [
    {
      "id": "a1b2c3d4-...",
      "storage_url": "/uploads/a1b2c3d4-....jpg",
      "device_uri": "ph://CC95F08C-...",
      "detected_objects": [],
      "emotions": [],
      "created_at": "2026-02-28T14:30:00"
    }
  ]
}
```

The mobile cleanup tab uses `device_uri` to call `MediaLibrary.deleteAssetsAsync` and remove the photo from the device.

---

### GET /photos/{user_id}

Returns the most recent photos stored for a user.

**Path + query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `user_id` | string | — | User identifier |
| `limit` | integer | 10 | Max photos to return |

**Example (curl)**
```bash
curl "http://localhost:8080/photos/00000000-0000-0000-0000-000000000001?limit=20"
```

**Response** `200`

Array of photo objects, same shape as the items in `/search/` response.

---

### GET /profiles/{user_id}

Returns face cluster profiles for a user. Each profile represents a distinct person detected across the photo library.

**Example (curl)**
```bash
curl http://localhost:8080/profiles/00000000-0000-0000-0000-000000000001
```

**Response** `200`
```json
[
  {
    "id": "person-uuid-...",
    "name": "Jake",
    "photo_count": 12,
    "cover_photo_url": "/uploads/3f2a1b4c-....jpg"
  },
  {
    "id": "person-uuid-2",
    "name": null,
    "photo_count": 5,
    "cover_photo_url": "/uploads/aa11bb22-....jpg"
  }
]
```

Unnamed profiles have `"name": null`. Use `/profiles/{person_id}/name` to assign a name.

---

### PATCH /profiles/{person_id}/name

Assign or update a name for a face cluster profile.

**Path parameters**

| Param | Description |
|---|---|
| `person_id` | Profile UUID (from `/profiles/{user_id}` response) |

**Request body** `application/json`

```json
{ "name": "Jake" }
```

**Example (curl)**
```bash
curl -X PATCH http://localhost:8080/profiles/person-uuid-... \
  -H "Content-Type: application/json" \
  -d '{"name": "Jake"}'
```

**Response** `200`
```json
{
  "ok": true,
  "person_id": "person-uuid-...",
  "name": "Jake"
}
```

---

### POST /clear/{user_id}

Wipes all data for a user: deletes all uploaded JPEG files from disk, removes all photo records from SQLite, and clears the Snowflake mirror if configured.

> **Destructive.** The mobile app calls this automatically on startup to reset state before re-uploading the latest camera roll.

**Example (curl)**
```bash
curl -X POST http://localhost:8080/clear/00000000-0000-0000-0000-000000000001
```

**Response** `200`
```json
{ "ok": true, "user_id": "00000000-0000-0000-0000-000000000001" }
```

---

## How Search Works

```
User types: "happy dog photos"
         ↓
POST /search/ { query, user_id }
         ↓
Load all photos from SQLite for user
Collect unique labels:
  object_labels = { "dog", "person", "car", "bicycle" }
  emotion_labels = { "happy", "neutral", "angry" }
         ↓
Gemini (text): "Given this query, which of these labels are relevant?"
  query:   "happy dog photos"
  labels:  ["dog", "person", "car", "bicycle"]
  emotions: ["happy", "neutral", "angry"]
  → Gemini returns: ["dog", "happy"]
         ↓
Filter photos: keep any photo where
  detected_objects contains "dog"
  OR emotions contains "happy"
         ↓
Return { ok, photos, matched_labels }
```

If Gemini returns an empty list (quota exceeded), all photos are returned unfiltered.

---

## How Narration Works

```
User taps "Narrate" on a photo
         ↓
POST /narrate/ { photo_id, user_id }
         ↓
SQLite lookup → detected_objects + emotions for this photo
Read /uploads/{photo_id}.jpg → raw bytes
         ↓
Gemini Vision (image + label hints):
  "Describe this photo. It contains: dog, person. Emotions: happy."
  → "A smiling woman and her golden retriever at a sunny park."
         ↓
(If Gemini quota exceeded → fallback description from labels)
         ↓
ElevenLabs TTS: text → MP3 (voice: Sarah, model: eleven_multilingual_v2)
Save to /uploads/narrations/{photo_id}_narrate.mp3
         ↓
Return { description, audio_url }
         ↓
Mobile plays audio via expo-av (works in iOS silent mode)
```

---

## Pipeline Flow

This is the full startup sequence in the mobile app:

```
App opens
  → Request MediaLibrary permission
  → Load up to 100 most recent photos from device
  → POST /clear/{user_id}                     wipe previous session
  → Upload 30 most recent photos (batched, 3 concurrent)
      → POST /upload/ per photo
          → returns { photo_id, storage_url }
          → photo_id stored in memory map (assetId → photo_id)
  → POST /reprocess/{user_id}
      → queues YOLO + DeepFace on all uploaded photos
      → runs as background tasks (non-blocking)
  → Poll GET /status/{user_id} every 3 seconds
      → shows "Processing X / 30..."
      → when processed >= total → stage = "Ready to Search"
```

After this pipeline completes, all photos have labels attached and search is active.

---

## Database Schema

**`photos` table** (SQLite)

| Column | Type | Description |
|---|---|---|
| `id` | TEXT | UUID primary key (from `/upload/`) |
| `user_id` | TEXT | User identifier |
| `storage_url` | TEXT | Relative path: `/uploads/{id}.jpg` |
| `device_uri` | TEXT | Device-side URI e.g. `ph://ASSET_ID` (iOS) |
| `caption` | TEXT | Optional text caption |
| `tags` | TEXT | JSON array of string tags |
| `detected_objects` | TEXT | JSON array: `[{ "label": "dog", "confidence": 0.91 }]` |
| `emotions` | TEXT | JSON array: `[{ "dominant_emotion": "happy", "emotion": {...} }]` |
| `person_ids` | TEXT | JSON array of people profile UUIDs |
| `importance_score` | REAL | Float 0.0–1.0 (1.0 = keep) |
| `low_value_flags` | TEXT | JSON array of flag strings (e.g. `["blur", "screenshot"]`) |
| `embedding` | TEXT | JSON float array for vector search (optional) |
| `created_at` | TEXT | ISO timestamp |

**`people` table** (SQLite)

| Column | Type | Description |
|---|---|---|
| `id` | TEXT | UUID primary key |
| `user_id` | TEXT | User identifier |
| `name` | TEXT | User-assigned name (nullable) |
| `embedding_centroid` | TEXT | JSON float array — average face embedding |
| `photo_count` | INTEGER | Number of photos this person appears in |
| `cover_photo_url` | TEXT | Representative photo for this profile |
| `created_at` | TEXT | ISO timestamp |

---

## API Keys Needed

| Service | Purpose | Free Tier |
|---|---|---|
| [Google Gemini](https://aistudio.google.com/app/apikey) | Search label matching (1 req/search) + photo description (1 req/narrate) | 1,500 req/day, 15 req/min |
| [ElevenLabs](https://elevenlabs.io) | Text-to-speech for narration | ~10,000 chars/month |
| [Snowflake](https://snowflake.com) | Metadata mirror (optional) | Free trial |

---

## Known Limitations

- **30-photo index limit** — `INDEX_LIMIT = 30` in the mobile app. Increase for larger demos.
- **Single demo user** — hardcoded `DEMO_USER_ID`. All users share the same photo pool.
- **No auth** — no login or per-user isolation.
- **Local disk storage** — photos and narration MP3s are not persistent across server restarts if the disk is wiped.
- **Gemini quota** — 1,500 free requests/day shared across search and narration. Fallback: search returns all photos, narration uses a label-based description.
- **People profiles** — backend infrastructure is built (face clustering, embeddings, people table) but the UI people tab is not fully wired up.

---

*Built at hackathon — February 2026*
