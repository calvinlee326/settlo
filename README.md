# Settlo

Split bills for dinners, trips, and more — in groups or one-on-one with friends. Settlo calculates who owes whom in as few transactions as possible.

## Features

- **Groups** — create a group, add expenses (split equally or with custom amounts), edit or remove them, and settle up with the fewest transactions.
- **Balances at a glance** — the home screen shows what you owe or are owed in each group, plus an overall net figure.
- **Friends & direct expenses** — add friends by phone, log one-on-one expenses outside any group, and track a running balance per friend.
- **Invitations** — invite someone to a group by phone (a pending invite appears on their home screen), by scanning a QR code, or by adding an existing friend.
- **Member management** — the creator can remove members and any member can leave a group; removal is blocked while that member still has expenses or settlements.
- **Payment history** — settled groups are archived to a dedicated history page.
- **PWA** — installable, mobile-first interface.

## Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, SQLite (dev) / PostgreSQL (prod), JWT auth
- **Frontend:** React 18, Vite, Tailwind CSS, React Router v6, Zustand, Axios, qrcode.react (PWA-ready)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit it, see below
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000 (docs at http://localhost:8000/docs).

`.env.example` ships a PostgreSQL URL. For local development set `DATABASE_URL=sqlite:///./settlo.db` and a `SECRET_KEY` of at least 32 characters. For local HTTP, also set `REFRESH_COOKIE_SECURE=false` and `REFRESH_COOKIE_SAMESITE=lax`. For production, use a managed PostgreSQL URL such as `postgresql+psycopg://...`.

To log in locally without a Twilio account, also set `DEV_OTP_CODE=000000`. `/verify` then accepts that fixed code for any phone number and no SMS is sent. Startup rejects it unless `DATABASE_URL` is SQLite, so it cannot be turned on in production.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at http://localhost:5173.

### Docker

```bash
docker compose up
```

Both services read `backend/.env`, so create it first.

### Tests

```bash
cd backend
python -m unittest discover -s tests -t .
```

The suite runs against in-memory SQLite and needs no Twilio credentials or running server.

## Deployment

The app is deployed as two services: the frontend on **Vercel** and the backend on **Railway**.

### Backend (Railway)

Set these variables on the Railway service:

- `DATABASE_URL` — managed PostgreSQL URL. Plain `postgres://` URLs are converted to `postgresql+psycopg://` automatically for SQLAlchemy and Alembic.
- `SECRET_KEY` — long random string (placeholder values are rejected at startup).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID` — Twilio Verify credentials for OTP delivery.
- `FRONTEND_URL` — the deployed frontend origin (e.g. `https://settlo-sooty.vercel.app`, no trailing slash). Required for CORS; requests from other origins are rejected.
- `EXTRA_ORIGINS` — optional comma-separated list of additional trusted origins. These origins can also use the cookie authentication endpoints; do not use wildcards.
- `REFRESH_COOKIE_SECURE=true` and `REFRESH_COOKIE_SAMESITE=none` — defaults required for the current cross-site Vercel/Railway deployment. `SameSite=none` with an insecure cookie is rejected at startup. Browsers that block third-party cookies may prevent session restoration; deploy frontend and API under the same site (for example `app.example.com` and `api.example.com`) to support those browsers reliably.

### Frontend (Vercel)

- Set `VITE_API_URL` to the Railway backend URL (e.g. `https://settlo-production.up.railway.app`).
- `frontend/vercel.json` rewrites all paths to `index.html` so client-side routes like `/login` work on direct load and refresh.

## Twilio Verify Setup

OTP delivery and verification are handled entirely by Twilio Verify — the backend never generates or stores OTP codes itself, and sending OTPs fails if Twilio is not configured. The one exception is the local `DEV_OTP_CODE` bypass described under Quick Start.

1. Create an account at [twilio.com](https://www.twilio.com) and copy the **Account SID** and **Auth Token** from the Console dashboard.
2. In the Console, go to **Verify → Services**, create a new Verify Service, and copy its **Service SID** (starts with `VA`).
3. Set the values in `backend/.env` (local) or the Railway service variables (production):

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_VERIFY_CHANNEL=sms
```

`TWILIO_VERIFY_CHANNEL` defaults to `sms`; Twilio Verify also supports channels such as `whatsapp` and `call`. On a Twilio trial account, OTPs can only be sent to phone numbers you have verified in the Twilio Console.

## Authentication

Phone-number login with OTP — no passwords.

1. Enter your phone number on `/login`.
2. A 6-digit OTP is delivered through Twilio Verify.
3. Enter the code on `/verify`. First-time numbers get an account automatically and are asked for a display name.
4. The app keeps a 30-minute access token in memory. A 7-day refresh token is set only as an HttpOnly cookie, scoped to `/api/auth`; it never appears in JSON or browser JavaScript storage. On reload the app restores the session using `/refresh` and `/me` before routing. Connection failures show a retry option without discarding the session.

Existing sessions stored in `settlo-auth` localStorage are removed on startup; users of the previous version need to sign in once. Refresh tokens in request bodies are no longer accepted. Verification, refresh, and logout require an exact trusted `Origin` header (including API clients). Logout revokes the cookie token and supplied access token before clearing the cookie; a network failure leaves logout available to retry.

Security: OTP is delivered and checked by Twilio Verify, OTP sends are rate-limited, logout blacklists tokens, and tokens are not persisted in browser storage.

## Settlement Algorithm

Each member's net balance = total paid − total owed. A greedy max-heap matching pairs the largest creditor with the largest debtor repeatedly, settling the group in at most n−1 transactions instead of the naive n². Settlements marked as paid are factored into future calculations.

This is a heuristic, not an optimum: finding the true minimum number of transactions is NP-hard (it reduces to set partition), so there are balance sets a subset-matching pass would settle in fewer transfers. The n−1 bound is a worst case that holds for any input, which is the guarantee worth having here.

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | /api/auth/send-otp | Send OTP |
| POST | /api/auth/verify-otp | Verify OTP, issue tokens |
| POST | /api/auth/set-username | Set display name |
| POST | /api/auth/logout | Blacklist token |
| POST | /api/auth/refresh | New access token |
| GET | /api/auth/me | Current user |
| POST/GET | /api/groups/ | Create / list groups |
| GET/DELETE | /api/groups/{id} | Detail / delete (creator only) |
| GET | /api/groups/{id}/invite | Invite token (QR / link) |
| GET/POST | /api/groups/join/{token} | Preview / join via invite |
| POST | /api/groups/{id}/members | Add a friend to the group |
| DELETE | /api/groups/{id}/members/{uid} | Remove member / leave group |
| POST/GET | /api/groups/{id}/expenses/ | Create / list expenses |
| PUT | /api/groups/{id}/expenses/{eid} | Edit expense |
| DELETE | /api/groups/{id}/expenses/{eid} | Delete expense |
| GET | /api/groups/{id}/settlements/ | Calculate settlements |
| POST | /api/groups/{id}/settlements/confirm | Settle the group and archive it |
| POST | /api/groups/{id}/settlements/{sid}/pay | Mark paid |
| POST/GET | /api/group-invitations | Invite by phone / list my pending invites |
| POST | /api/group-invitations/{id}/accept | Accept group invite |
| POST | /api/group-invitations/{id}/decline | Decline group invite |
| POST/GET | /api/friends/requests | Send / list friend requests |
| POST | /api/friends/requests/{id}/accept | Accept friend request |
| POST | /api/friends/requests/{id}/decline | Decline friend request |
| GET | /api/friends | List friends with net balances |
| DELETE | /api/friends/{id} | Remove friend |
| POST | /api/friends/{id}/settle | Settle up with a friend |
| GET | /api/friends/{id}/expenses | Direct expenses with a friend |
| POST | /api/direct-expenses | Create a direct expense |
| DELETE | /api/direct-expenses/{id} | Delete a direct expense |
