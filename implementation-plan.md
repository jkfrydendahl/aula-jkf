# Aula-JKF Production Setup Specification

## Purpose

This document defines the production hardening and deployment plan for `aula-jkf`.

The current smoke test has proven that:

* The backend runs successfully on a Webdock Denmark VPS.
* Webdock’s Danish IP can complete MitID login against Aula.
* Aula data retrieval works.
* At least one POST call works.
* Token persistence survives backend/container restart.
* The local test architecture worked through an SSH tunnel:

  * local frontend → local SSH tunnel → Webdock backend → Aula.

The next goal is to move from smoke test to a safe production setup:

```text
Vercel frontend
  ↓
Secured HTTPS API domain
  ↓
Webdock reverse proxy
  ↓
FastAPI backend bound to 127.0.0.1:8000
  ↓
Aula
```

The backend must not be publicly usable without the PWA’s own access protection.

---

# Phase 1 — Backend Security and App-Level Authentication

## Goal

Prevent unauthenticated public access to any backend endpoint that can read, write, refresh, expose, or operate using stored Aula tokens.

The current backend stores Aula tokens server-side. Once those tokens exist, unprotected API routes become sensitive. Before exposing the backend publicly, add an application-level protection layer.

## Required outcome

A browser user must authenticate to the PWA/backend before accessing Aula-backed endpoints.

Unauthenticated users may only access a minimal public health endpoint and, if needed, the app-login endpoint.

## Recommended implementation

Implement a simple private-app authentication layer suitable for personal/family use.

### Environment variables

Add:

```env
APP_AUTH_ENABLED=true
APP_AUTH_PASSWORD=<strong-random-password>
APP_SESSION_SECRET=<strong-random-secret>
APP_SESSION_COOKIE_NAME=aula_jkf_session
APP_SESSION_TTL_SECONDS=604800
```

Optional:

```env
APP_ALLOWED_ORIGINS=https://<vercel-app-domain>
```

`APP_SESSION_SECRET` must be used to sign/encrypt session tokens.

Generate secrets with:

```bash
openssl rand -hex 32
```

## Authentication flow

Add endpoints:

```http
POST /app-auth/login
POST /app-auth/logout
GET  /app-auth/me
```

### `POST /app-auth/login`

Request:

```json
{
  "password": "user entered password"
}
```

Behavior:

* Compare against `APP_AUTH_PASSWORD`.
* On success, issue a signed session cookie.
* On failure, return `401`.

Response on success:

```json
{
  "authenticated": true
}
```

### Cookie requirements

For production cross-origin frontend/API deployment, use:

```text
HttpOnly
Secure
SameSite=None
Path=/
```

If the frontend and API are later placed under the same parent domain, `SameSite=Lax` may be acceptable, but `SameSite=None; Secure` is safer for the Vercel + separate API-domain setup.

### Frontend fetch behavior

All frontend API calls that rely on session cookies must use:

```ts
credentials: "include"
```

## Route protection

Add a backend dependency/middleware, for example:

```python
require_app_auth
```

Apply it to all Aula-backed or sensitive routes.

Protect at minimum:

```text
/auth/check
/auth/start
/auth/status/{flow_id}
/auth/select-identity/{flow_id}
/children
/presence/*
/messages*
/posts*
/calendar*
/vacation*
/push*
/sync*
/admin*
```

The exact route list should be confirmed against the existing FastAPI routers.

Leave public:

```text
GET /health
POST /app-auth/login
```

Optionally public:

```text
GET /
```

But `/` must not expose sensitive token/auth state.

## Health endpoint split

Add or confirm:

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

This endpoint must not reveal:

* whether Aula tokens exist;
* user identity;
* children names;
* institutions;
* token expiry;
* internal file paths.

`/auth/check` should require app authentication.

## CORS requirements

Production CORS must not use wildcard origins.

Allowed origins should come from env.

Example:

```env
AULA_FRONTEND_URL=https://<vercel-app-domain>
```

For local development, allow:

```env
AULA_FRONTEND_URL=http://localhost:3000,http://127.0.0.1:3000
```

Backend CORS must support credentials if session cookies are used:

```text
Access-Control-Allow-Credentials: true
```

## Frontend requirements

Add a simple login screen/gate:

* On app load, call `/app-auth/me`.
* If unauthenticated, show password form.
* After successful login, load normal app.
* On logout, call `/app-auth/logout`.

Do not store the app password in frontend code or `NEXT_PUBLIC_*` variables.

## Acceptance criteria

Phase 1 is complete when:

* Unauthenticated request to `/children` returns `401`.
* Unauthenticated request to `/messages` returns `401`.
* Unauthenticated request to `/auth/check` returns `401`.
* `GET /health` returns `200`.
* `POST /app-auth/login` with wrong password returns `401`.
* `POST /app-auth/login` with correct password returns `200` and sets a secure session cookie.
* Authenticated frontend can perform all existing Aula features.
* MitID login still works.
* Token persistence still works after container restart.

---

# Phase 2 — Webdock Production Deployment and Reverse Proxy

## Goal

Run the backend persistently on Webdock, but keep the FastAPI container bound to localhost only. Public access must go through HTTPS reverse proxy.

## Current confirmed server

```text
Provider: Webdock
Location: Europe / Denmark
IPv4: 193.181.210.163
User: admin
Backend container: aula-jkf-backend
Backend internal port: 8000
Current binding: 127.0.0.1:8000->8000
Token data path: /opt/aula-jkf/data
Backend env file: /opt/aula-jkf/backend.env
```

## Target server layout

```text
/opt/aula-jkf/
  aula-jkf/              # cloned git repo
  data/                  # persistent token/push storage
  backend.env            # production backend env file
  docker-compose.yml     # optional, recommended for production
```

## Docker setup

Use either Docker Compose or a documented `docker run` command.

Recommended: add `docker-compose.yml` outside the repo or in a deployment folder.

Example:

```yaml
services:
  backend:
    image: aula-jkf-backend:latest
    container_name: aula-jkf-backend
    restart: unless-stopped
    env_file:
      - /opt/aula-jkf/backend.env
    volumes:
      - /opt/aula-jkf/data:/app/data
    ports:
      - "127.0.0.1:8000:8000"
```

If Docker Compose is not available from the default Ubuntu repository, either:

* continue using `docker run`, or
* install Docker’s official repository and Compose plugin later.

Do not bind backend to:

```text
0.0.0.0:8000
```

## Backend production env

Example:

```env
AULA_FRONTEND_URL=https://<vercel-app-domain>
AULA_TOKEN_STORE_PATH=/app/data/tokens.json
AULA_PUSH_STORE_PATH=/app/data/push_subs.json
AULA_POLL_INTERVAL=300

AULA_VAPID_PRIVATE_KEY=<value-if-push-is-used>
AULA_VAPID_PUBLIC_KEY=<value-if-push-is-used>
AULA_VAPID_CLAIM_EMAIL=mailto:jesperfrydendahl@outlook.com

AULA_ADMIN_SECRET=<strong-random-secret>
AULA_SYNC_TARGET_URL=

APP_AUTH_ENABLED=true
APP_AUTH_PASSWORD=<strong-random-password>
APP_SESSION_SECRET=<strong-random-secret>
APP_SESSION_COOKIE_NAME=aula_jkf_session
APP_SESSION_TTL_SECONDS=604800
```

## Reverse proxy

Use Caddy or Nginx.

Recommended for simplicity: Caddy.

Target:

```text
https://api.<your-domain>
  → reverse_proxy 127.0.0.1:8000
```

Example Caddyfile:

```caddy
api.<your-domain> {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy should handle HTTPS automatically if DNS points correctly to the Webdock server.

## Firewall

Allow:

```text
22/tcp   SSH
80/tcp   HTTP for certificate challenge / redirect
443/tcp  HTTPS API
```

Do not allow:

```text
8000/tcp public
```

Example:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw enable
```

Confirm backend is not public:

```bash
curl http://127.0.0.1:8000/health
```

From outside the server, direct access to `http://193.181.210.163:8000` should fail.

## Deployment commands

Document the final deployment command.

If not using Compose:

```bash
cd /opt/aula-jkf/aula-jkf/backend

sudo docker build -t aula-jkf-backend:latest .

sudo docker rm -f aula-jkf-backend

sudo docker run -d \
  --name aula-jkf-backend \
  --restart unless-stopped \
  --env-file /opt/aula-jkf/backend.env \
  -v /opt/aula-jkf/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  aula-jkf-backend:latest
```

## Acceptance criteria

Phase 2 is complete when:

* `curl http://127.0.0.1:8000/health` works on Webdock.
* `https://api.<your-domain>/health` works externally.
* `http://193.181.210.163:8000` does not work externally.
* Backend container restarts automatically.
* Token persistence survives container rebuild/restart.
* Reverse proxy logs and Docker logs are accessible.
* HTTPS certificate is valid.
* No sensitive endpoint is reachable without app auth.

---

# Phase 3 — Vercel Frontend Production Setup

## Goal

Point the Vercel-hosted frontend at the secured Webdock backend and confirm the full PWA works in production.

## Vercel environment variables

Set in Vercel project settings:

```env
NEXT_PUBLIC_API_URL=https://api.<your-domain>
```

Do not include private secrets in `NEXT_PUBLIC_*` variables.

Do not put the app auth password in Vercel frontend env.

If additional frontend-only config exists, document it separately.

## Backend CORS

Update `/opt/aula-jkf/backend.env` on Webdock:

```env
AULA_FRONTEND_URL=https://<vercel-app-domain>
```

If using both Vercel preview and production domains, include both:

```env
AULA_FRONTEND_URL=https://<production-domain>,https://<preview-domain>
```

Use preview domains carefully. The stricter option is to allow only the production frontend domain.

After changing backend env, recreate the backend container.

## Frontend changes

Ensure all API requests use:

```ts
credentials: "include"
```

where session-cookie authentication is required.

Confirm the frontend login gate works:

1. Load Vercel app.
2. If not app-authenticated, show password screen.
3. Submit correct password.
4. App loads.
5. Aula auth/check works.
6. Existing Aula token is detected, or MitID flow can be started.

## Production MitID/Aula flow

Test:

* Existing token detection.
* Fresh MitID login.
* Identity selection if applicable.
* Dashboard load.
* Children data.
* Messages/posts/calendar.
* Tested POST actions.
* Token persistence after backend restart.
* Token refresh later.

## PWA behavior

Confirm:

* install prompt / add-to-home-screen behavior still works;
* manifest and icons still load;
* service worker does not cache stale API responses incorrectly;
* app works after hard refresh;
* app handles backend unauthenticated state gracefully.

## Acceptance criteria

Phase 3 is complete when:

* Vercel frontend calls `https://api.<your-domain>`, not localhost.
* Browser DevTools shows no CORS errors.
* App-level login works from Vercel.
* Unauthenticated users cannot access sensitive backend data.
* Authenticated user can access existing Aula data.
* Fresh MitID login works from production.
* POST calls still work.
* Backend token persistence still works.
* The PWA is usable from desktop and mobile browser.

---

# Phase 4 — Documentation, Cleanup, and Operational Hardening

## Goal

Make the deployment understandable, repeatable, and safe to maintain.

## Documentation updates

Update or create:

```text
README.md
DEPLOYMENT.md
PRODUCTION_SETUP_SPEC.md
docs/webdock-production.md
docs/security.md
```

## README changes

The README should clearly state:

* Railway/generic cloud deployment may fail due to Aula/STIL IP filtering.
* Webdock Denmark VPS has been tested successfully.
* Raspberry Pi/residential IP remains an alternative, not the only viable path.
* Production backend must not be exposed without authentication.

## DEPLOYMENT.md changes

Split deployment into:

```text
1. Local development
2. Webdock smoke test via SSH tunnel
3. Webdock production backend
4. Vercel frontend
5. Optional Raspberry Pi / residential fallback
```

Remove or clearly mark Railway deployment as obsolete/experimental if it is no longer recommended.

## Add smoke test documentation

Document the exact smoke test that worked:

```text
Backend:
Webdock Docker container bound to 127.0.0.1:8000

SSH tunnel:
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -N -L 127.0.0.1:8001:127.0.0.1:8000 admin@193.181.210.163

Local frontend:
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001

Local browser:
http://localhost:3000
```

Document expected test response:

```bash
curl.exe -i http://127.0.0.1:8001/auth/check -H "Origin: http://localhost:3000"
```

Expected before Aula login:

```json
{"authenticated":false,"reason":"no_tokens"}
```

Expected CORS header:

```text
access-control-allow-origin: http://localhost:3000
```

## Add operational commands

Document:

### Check backend status

```bash
sudo docker ps -a
sudo docker logs aula-jkf-backend --tail 100
curl http://127.0.0.1:8000/health
```

### Rebuild backend

```bash
cd /opt/aula-jkf/aula-jkf
git pull

cd backend
sudo docker build -t aula-jkf-backend:latest .

sudo docker rm -f aula-jkf-backend

sudo docker run -d \
  --name aula-jkf-backend \
  --restart unless-stopped \
  --env-file /opt/aula-jkf/backend.env \
  -v /opt/aula-jkf/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  aula-jkf-backend:latest
```

### Restart backend

```bash
sudo docker restart aula-jkf-backend
```

### Check token persistence

```bash
sudo docker restart aula-jkf-backend
curl http://127.0.0.1:8000/auth/check
```

## Security documentation

Document:

* Aula tokens are stored server-side.
* `/opt/aula-jkf/data` must be protected.
* `/opt/aula-jkf/backend.env` must be protected.
* The backend must not bind to public `0.0.0.0:8000`.
* Sensitive endpoints must require app authentication.
* `NEXT_PUBLIC_*` variables are visible to browser users and must never contain secrets.
* If session cookies are used cross-origin, CORS and cookie settings must be deliberate.

## Backup plan

Add simple backups for:

```text
/opt/aula-jkf/data
/opt/aula-jkf/backend.env
```

Recommended:

* manual backup before major updates;
* optional encrypted backup;
* never commit token files or env files to git.

## Git hygiene

Ensure `.gitignore` excludes:

```text
backend.env
.env
.env.local
tokens.json
push_subs.json
data/
```

## Deployment validation checklist

Before calling production complete:

```text
[ ] Backend runs on Webdock.
[ ] Backend binds only to 127.0.0.1:8000.
[ ] HTTPS API domain works.
[ ] Direct public port 8000 does not work.
[ ] Vercel frontend uses HTTPS API URL.
[ ] Production CORS only allows intended frontend domain.
[ ] App-level auth protects sensitive routes.
[ ] Aula login works.
[ ] Aula data retrieval works.
[ ] POST actions work.
[ ] Token persistence works after restart.
[ ] Backend logs are readable.
[ ] Deployment docs are updated.
[ ] Secrets are not committed.
[ ] README no longer implies Railway is the preferred production path.
```

---

# Implementation Order for Copilot

Copilot should implement in small, reviewable steps.

## Step 1

Add backend app-auth settings and session utilities.

## Step 2

Add `/app-auth/login`, `/app-auth/logout`, `/app-auth/me`.

## Step 3

Protect all sensitive backend routes.

## Step 4

Update frontend API helper to support `credentials: "include"`.

## Step 5

Add frontend password gate.

## Step 6

Add safe `/health` endpoint.

## Step 7

Add production deployment docs.

## Step 8

Add Webdock-specific deployment notes.

Do not change the Aula integration logic unless required for route protection.

Do not expose tokens to the frontend.

Do not put secrets in `NEXT_PUBLIC_*` variables.

Do not bind backend publicly.

---

# Final Production Principle

The production setup is only acceptable if this remains true:

```text
A public visitor can reach the frontend,
but cannot use the backend’s stored Aula session
unless they first pass the PWA’s own authentication layer.
```
