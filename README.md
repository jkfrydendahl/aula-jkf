# Aula JKF

Aula JKF is a private FastAPI + Next.js PWA for accessing Aula with MitID login, family-specific accounts, and push notifications.

> **Note:** This is a personal deployment. Only whitelisted accounts can use this instance. If you want to try it out, create your own copy from the source code — or contact the author.

## Production setup

- **Frontend:** Next.js PWA on **Vercel**
- **Backend:** FastAPI in **Docker** on a **Webdock VPS** at `YOUR_VPS_IP`
- **Server path:** `/opt/aula-jkf/`
- **Backend env file:** `/opt/aula-jkf/backend.env`
- **Persistent data:** `/opt/aula-jkf/data/`
- **HTTPS:** Nginx on the VPS reverse-proxies traffic to the backend container
- **Browser API access:** the frontend sends browser requests through `frontend/app/api/[...path]/route.ts`

The Next.js proxy route is intentional: it keeps browser traffic same-origin and allows cookies to work correctly in the iOS Safari PWA.

## Features

- **MitID login** with QR code support
- **Dashboard** with children presence and check-in/out times
- **Pickup registration** for all 4 supported activity types
- **Sick registration**
- **Messages** with read/unread toggle
- **Posts** for institution announcements
- **Vacation registration** with per-day responses
- **Push notifications** with VAPID-based web push
- **Multi-user support** with isolated token and push storage per family member
- **Installable PWA** on iOS and Android
- **Auto-refresh**
  - presence every 60 seconds
  - content every 5 minutes
  - refresh on visibility change when the app becomes active again

## Login flow

1. Open the app
2. Select the user by name
3. Enter that user's app password
4. If Aula tokens exist, the user is signed in
5. If tokens are missing, the app shows **Login påkrævet**
6. Start the MitID flow
7. Enter the user's MitID username
8. Complete the approval flow, typically using the QR code

### Important login notes

- Tokens renew silently in normal use
- MitID re-authentication is usually only needed when the refresh token expires

## Multi-user support

Each family member has their own configuration:

- `APP_USER_N_NAME`
- `APP_USER_N_PASSWORD`
- `APP_USER_N_TOKEN_PATH`
- `APP_USER_N_PUSH_STORE_PATH`

Each user therefore has:

- a separate app password
- a separate MitID identity
- a separate Aula token store
- a separate push subscription store

## Local development

### Requirements

- Python with `venv`
- Node.js and npm

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env`, then start the API:

```bash
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

### Local frontend against the Webdock backend

If you want to run the frontend locally while using the backend on the VPS, open an SSH tunnel:

```bash
ssh -L 8000:localhost:8000 admin@YOUR_VPS_IP
```

Then use:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

This is useful when the backend on Webdock already has working Aula tokens.

## Push notifications

- Uses VAPID-based web push
- Stores subscriptions per user
- Polls for updates every 5 minutes in the background
- Works well with the installed PWA on mobile devices

## Operations

- If the app shows **Login påkrævet**, start a fresh MitID login in the app
- To reset one user's Aula tokens, remove that user's token file under `/opt/aula-jkf/data/`
- To change an app password, edit `/opt/aula-jkf/backend.env` and recreate the backend container
- `docker restart` does **not** re-read `backend.env`

See `DEPLOYMENT.md` for deployment and operational details.

## Roadmap

Planned, but not implemented yet:

- Calendar view
- Galleries
- Compose/send messages
- PWA icons (proper 192×512 branded icons)

## Credits

Built on top of [scaarup/aula](https://github.com/scaarup/aula) — an unofficial Python client for the Danish school platform Aula. The `aula_login_client` and `aula_client` modules are derived from that work.
