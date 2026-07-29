# PetMood AI — Backend API

AI-powered pet mood detection REST API built with FastAPI, PostgreSQL, and JWT authentication.

## Live API
https://petmood-ai-production.up.railway.app/docs

## Tech Stack
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- JWT Authentication (python-jose)
- Deployed on Railway

## Endpoints
- POST /auth/register
- POST /auth/login
- GET/POST /pets/
- GET/PATCH/DELETE /pets/{pet_id}
- POST /pets/{pet_id}/scans
- GET /pets/{pet_id}/scans/{scan_id}