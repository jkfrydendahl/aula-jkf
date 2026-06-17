# Deployment Guide

This project uses a split production deployment:

- **Frontend:** Next.js PWA on **Vercel**
- **Backend:** FastAPI in **Docker** on a **Webdock VPS** at `193.181.210.163`

## Production architecture

### Backend

- SSH user: `admin`
- Host: `193.181.210.163`
- Project directory: `/opt/aula-jkf/`
- Environment file: `/opt/aula-jkf/backend.env`
- Persistent data directory: `/opt/aula-jkf/data/`
- Reverse proxy: Nginx
- Container bind: `127.0.0.1:8000:8000`

The data directory contains per-user Aula token files and per-user push subscription stores.

### Frontend

- Hosted on Vercel
- Deployed automatically from GitHub on push to `main`
- Browser requests go through the Next.js API proxy route at `/api/[...path]`
- The proxy forwards traffic to the backend so cookies remain same-origin in the PWA, especially on iOS Safari

## Production environment

### Backend environment file

Path:

```text
/opt/aula-jkf/backend.env
```

Required settings:

| Variable | Purpose |
| --- | --- |
| `APP_AUTH_ENABLED` | Enables the app's password-based login gate. Set to `true` in production. |
| `APP_SESSION_SECRET` | Strong random secret used for app sessions. Use at least 32 characters. |
| `APP_USER_1_NAME` | Display name for the first family member. |
| `APP_USER_1_PASSWORD` | App password for the first family member. |
| `APP_USER_1_TOKEN_PATH` | Token store path for the first family member. Production path: `/app/data/tokens_user1.json`. |
| `APP_USER_1_PUSH_STORE_PATH` | Push subscription store path for the first family member. Production path: `/app/data/push_user1.json`. |
| `APP_USER_2_NAME` | Display name for the second family member. |
| `APP_USER_2_PASSWORD` | App password for the second family member. |
| `APP_USER_2_TOKEN_PATH` | Token store path for the second family member. Production path: `/app/data/tokens_user2.json`. |
| `APP_USER_2_PUSH_STORE_PATH` | Push subscription store path for the second family member. Production path: `/app/data/push_user2.json`. |
| `AULA_VAPID_PRIVATE_KEY` | Private VAPID key for web push. |
| `AULA_VAPID_PUBLIC_KEY` | Public VAPID key for web push. |
| `AULA_VAPID_CLAIM_EMAIL` | Mailto identity used in the VAPID claim. |

### Frontend environment on Vercel

Set:

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Public HTTPS origin for the backend served by Nginx on the Webdock VPS. |

## Backend deployment on Webdock

SSH to the server:

```bash
ssh admin@193.181.210.163
```

Deploy with the exact commands currently used in production:

```bash
cd /opt/aula-jkf
git pull
docker build -t aula-jkf-backend ./backend
docker rm -f aula-jkf-backend
docker run -d --name aula-jkf-backend --env-file backend.env \
  -v /opt/aula-jkf/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  aula-jkf-backend
```

## Frontend deployment on Vercel

The frontend deploys automatically when changes are pushed to `main` through the Vercel GitHub integration.

No separate manual frontend deploy step is part of the normal production workflow.

## Authentication and MitID operations

### Residential IP requirement

MitID login must happen from a **residential IP**.

Aula/STIL blocks authentication requests from datacenter IPs, so the initial login and any later re-authentication must be completed by a real user through the app on a residential connection.

### Normal login and re-auth flow

1. Open the app
2. Select the user by name
3. Enter the app password
4. If tokens are missing, the app shows **Login påkrævet**
5. Tap **Log ind med MitID**
6. Enter the user's MitID username
7. Complete the approval flow, usually with the QR code

### Token renewal behavior

- Access tokens renew silently
- MitID is normally only needed again when the refresh token expires
- Re-authentication is therefore uncommon in day-to-day use

## Resetting tokens

To force a new MitID login for one user, remove that user's token file from the data directory and then recreate the backend container.

Example paths:

- `/opt/aula-jkf/data/tokens_user1.json`
- `/opt/aula-jkf/data/tokens_user2.json`

After that, the app will show **Login påkrævet** for that user.

## Changing app passwords

To change a user's app password:

1. Edit `/opt/aula-jkf/backend.env`
2. Update the relevant `APP_USER_N_PASSWORD`
3. Recreate the container

Use:

```bash
cd /opt/aula-jkf
docker rm -f aula-jkf-backend
docker run -d --name aula-jkf-backend --env-file backend.env \
  -v /opt/aula-jkf/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  aula-jkf-backend
```

### Important

`docker restart` does **not** re-read `backend.env`.

If environment variables changed, always remove and recreate the container.

## Local development

### Local backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Use `backend/.env` for local backend configuration.

### Local frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Local frontend against the Webdock backend over SSH tunnel

If you want to run the frontend locally but use the backend on the VPS:

```bash
ssh -L 8000:localhost:8000 admin@193.181.210.163
```

Then set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Operational notes

- Check that the backend container is running after each backend deploy
- Check that Nginx still forwards HTTPS traffic to `127.0.0.1:8000`
- Check that Vercel still has the correct `NEXT_PUBLIC_API_URL`
- If a single user loses notifications, inspect that user's push store in `/opt/aula-jkf/data/`
- If a single user is forced back to **Login påkrævet**, inspect that user's token file and refresh-token state
