# Aula PWA

A standalone Progressive Web App for [Aula](https://aula.dk) (Danish school communication platform). Forked from [scaarup/aula](https://github.com/scaarup/aula) Home Assistant integration — rebuilt as a full-stack web app.

## Features

- **MitID login** — full OAuth/SAML flow, QR code support
- **Dashboard** — children's presence status, check-in/out times
- **Pickup registration** — all 4 Aula activity types (pickup, self-decider, send home, go home with)
- **Sick registration** — mark/unmark children as sick
- **Messages** — read threads, view attachments, mark as read
- **Posts** — institution posts with full content
- **Vacation registration** — view and respond to vacation surveys
- **Calendar** — school calendar events
- **Auto-refresh** — presence every 60s, content every 5min, visibility-aware
- **Toast notifications** — non-intrusive feedback on actions

## Architecture

```
frontend/          Next.js 14 PWA (Vercel or self-hosted)
backend/           FastAPI Python backend
  app/
    aula_client.py          Aula API client
    aula_login_client/      MitID OAuth/SAML login flow
    services/               Business logic layer
    routers/                REST API endpoints
    middleware/             Token refresh middleware
```

## Requirements

- **Must run on a residential IP** — Aula/STIL blocks all datacenter IPs (Railway, AWS, Vercel serverless, etc.)
- Recommended: Raspberry Pi + Cloudflare Tunnel for remote access
- Python 3.12+, Node.js 18+

## Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # edit with your settings
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000` and log in with MitID.

## Deployment (Raspberry Pi + Cloudflare Tunnel)

> **Why not cloud hosting?** Aula/STIL actively blocks datacenter IPs at the network level.
> Both the API and token refresh endpoints return 403 from any cloud provider.
> This is the same reason the original integration only works on Home Assistant (which runs locally).

**TODO:** Docker Compose + Cloudflare Tunnel setup instructions.

## Known Limitations

- MitID login requires residential IP (home network)
- Guardian login only (child login not supported)
- "Registrér ankomst" (check-in) API not yet discovered for parent role

## Credits

- Original Aula integration: [scaarup/aula](https://github.com/scaarup/aula)
- MitID login flow reverse-engineered from the original HA component
