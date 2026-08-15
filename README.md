# PetMood AI — Backend API

AI-powered pet mood detection REST API. A user uploads a short video of their pet (plus optional
supporting photos and a free-text behavior description), and the API runs it through Google Gemini to
return a mood, confidence score, summary, and actionable suggestions.

**Two repos, work together**: this is the backend only. The Android frontend lives in a sibling repo at
`../petmood-ai` (own git history, own deploys) — not a submodule.

## Live API
https://petmoodai-au.azurewebsites.net/docs

Deployed on Azure App Service `PetmoodAI-AU` (resource group `petmood-rg`, region `australiaeast` — must
stay a Gemini-supported region).

## Tech Stack
- FastAPI 0.136.3
- PostgreSQL (Azure Postgres Flexible Server, via `psycopg2-binary`) — SQLite is only a local-dev fallback
- SQLAlchemy 2.0.50 + Alembic 1.18.5 for migrations
- JWT authentication (`python-jose`), password hashing via `pwdlib`
- `google-genai` 2.16.0 (model `gemini-flash-latest`) for mood analysis
- Deployed via GitHub Actions (`.github/workflows/main_petmoodai_au.yml`) on push to `main`

## Architecture notes
- `main.py`'s `lifespan` runs `alembic upgrade head` on **every app startup** — migrations are not a
  separate manual deploy step.
- Scan analysis is async: `POST /pets/{id}/scans` returns `status: "processing"` immediately; a
  `BackgroundTask` uploads the video to Gemini, polls until it's active, and writes
  `mood_result`/`confidence`/`summary`/`suggestions`/`error_message` back onto the `Scan` row. Poll
  `GET /pets/{id}/scans/{scan_id}` for the result.
- A scan's video is always required; 0-3 supporting photos and an optional text description ride along in
  the *same* `POST /pets/{id}/scans` request (multipart fields `file`/`photos`/`description`) — there is
  no separate endpoint for photo-only or description-only scans. `gemini_client.analyze_pet_scan()` is the
  one entry point that combines all three into a single Gemini call.
- Scans are rate-limited to 5/hour per user (each one costs a Gemini API call).

## Endpoints
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/users/me`
- `GET/POST /pets/`
- `GET/PATCH/DELETE /pets/{pet_id}`
- `POST /pets/{pet_id}/scans` — multipart: required `file` (video), optional `photos` (≤3 images),
  optional `description` (≤1000 chars)
- `GET /pets/{pet_id}/scans` — list all scans for a pet
- `GET /pets/{pet_id}/scans/{scan_id}` — poll for analysis result
- `GET /pets/{pet_id}/latest-scan`

## Local development
```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m alembic upgrade head   # also runs automatically on every app startup
.venv/bin/uvicorn main:app --reload
```

Required environment variables (`.env`):
- `SECRET_KEY` — JWT signing secret
- `GEMINI_API_KEY` — Google Gemini API key
- `DATABASE_URL` — optional; falls back to local SQLite (`sqlite:///./petmood.db`) if unset