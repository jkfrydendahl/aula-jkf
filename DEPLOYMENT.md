# Deployment Guide

## Architecture

- **Frontend**: Next.js PWA → Vercel
- **Backend**: FastAPI → Railway (with persistent volume)

## Backend (Railway)

### Setup
1. Create a new Railway project
2. Connect this repo, set root directory to `backend/`
3. Railway will auto-detect the Dockerfile

### Environment Variables
```
AULA_FRONTEND_URL=https://your-app.vercel.app
AULA_TOKEN_STORE_PATH=/app/data/tokens.json
AULA_PUSH_STORE_PATH=/app/data/push_subs.json
AULA_VAPID_PRIVATE_KEY=<generate with web-push>
AULA_VAPID_PUBLIC_KEY=<generate with web-push>
AULA_VAPID_CLAIM_EMAIL=mailto:your@email.com
```

### Persistent Storage
Attach a Railway volume mounted at `/app/data` to persist tokens between deploys.

Without this, you'll need to re-authenticate via MitID after every deploy.

## Frontend (Vercel)

### Setup
1. Create a new Vercel project
2. Connect this repo, set root directory to `frontend/`
3. Vercel will auto-detect Next.js

### Environment Variables
```
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

## Post-Deploy Checklist

1. Deploy backend first → get the Railway URL
2. Set `NEXT_PUBLIC_API_URL` in Vercel → deploy frontend
3. Set `AULA_FRONTEND_URL` in Railway → redeploy backend
4. Open frontend → login with MitID (first time only)
5. Verify dashboard loads with children data

## Local Development

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```
