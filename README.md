# Settlo

Split bills for dinners, trips, and more — in groups or one-on-one with friends. Settlo calculates who owes whom in as few transactions as possible.

Live: [settlo-sooty.vercel.app](https://settlo-sooty.vercel.app)

User guide: [How to use Settlo](https://drive.google.com/file/d/1BXuILHMtLOUc_Va8OepIizgRT80EmiHY/view?usp=sharing)

Support: [ko-fi.com/chunchenglee](https://ko-fi.com/chunchenglee)

## Features

- **Google sign-in & IDs** — sign in with Google; each user picks a unique, case-insensitive ID that friends use to find them.
- **Groups** — create a group, add expenses (split equally between any subset of members, or with custom amounts), edit or remove them, and settle up with the fewest transactions.
- **Balances at a glance** — the home screen shows what you owe or are owed in each group, plus an overall net figure.
- **Friends & direct expenses** — add friends by ID, log one-on-one expenses outside any group, and track a running balance per friend.
- **Invitations** — invite someone to a group by ID (a pending invite appears on their home screen), by sharing the group's invite link, or by adding an existing friend.
- **Member management** — the creator can remove members and any member can leave a group; removal is blocked while that member still has expenses or settlements.
- **Payment history** — settled groups are archived to a dedicated history page.
- **PWA** — installable, mobile-first interface (on iPhone: open in Safari → **Share** → **Add to Home Screen**).
- **Privacy policy** — public at `/privacy`, linked from the login page.

## Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, SQLite (dev) / PostgreSQL (prod), JWT auth, Google ID token verification (PyJWT)
- **Frontend:** React 18, Vite, Tailwind CSS, React Router v6, Zustand, Axios, Google Identity Services (PWA-ready)

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

To sign in locally, set `GOOGLE_CLIENT_ID` in `backend/.env` and the same value as `VITE_GOOGLE_CLIENT_ID` in `frontend/.env.local`, with `http://localhost` and `http://localhost:5173` as authorized origins (see Authentication below).

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

The suite runs against in-memory SQLite and needs no Google credentials or running server.

## Deployment

The app is deployed as two services: the frontend on **Vercel** and the backend on **Railway**.

### Backend (Railway)

Set these variables on the Railway service:

- `DATABASE_URL` — managed PostgreSQL URL. Plain `postgres://` URLs are converted to `postgresql+psycopg://` automatically for SQLAlchemy and Alembic.
- `SECRET_KEY` — long random string (placeholder values are rejected at startup).
- `GOOGLE_CLIENT_ID` — OAuth web client ID; required, since Google is the only way to sign in (see below). Must match the frontend's `VITE_GOOGLE_CLIENT_ID`.
- `FRONTEND_URL` — the deployed frontend origin (e.g. `https://settlo-sooty.vercel.app`, no trailing slash). Required for CORS; requests from other origins are rejected.
- `EXTRA_ORIGINS` — optional comma-separated list of additional trusted origins. These origins can also use the cookie authentication endpoints; do not use wildcards.
- `REFRESH_COOKIE_SECURE=true` and `REFRESH_COOKIE_SAMESITE=none` — defaults required for the current cross-site Vercel/Railway deployment. `SameSite=none` with an insecure cookie is rejected at startup. Browsers that block third-party cookies may prevent session restoration; deploy frontend and API under the same site (for example `app.example.com` and `api.example.com`) to support those browsers reliably.

### Frontend (Vercel)

- Set `VITE_API_URL` to the Railway backend URL (e.g. `https://settlo-production.up.railway.app`).
- Set `VITE_GOOGLE_CLIENT_ID` (required; the login page has no other way in). It is baked in at build time, so redeploy after changing it.
- `frontend/vercel.json` rewrites all paths to `index.html` so client-side routes like `/login` work on direct load and refresh.

## Authentication

Sign-in is Google only — no passwords, no SMS.

1. Click **Continue with Google** on `/login`. A first-time Google account gets a Settlo account automatically, named from the Google profile (or the email address if Google has no name).
2. The app keeps a 30-minute access token in memory. A 7-day refresh token is set only as an HttpOnly cookie, scoped to `/api/auth`; it never appears in JSON or browser JavaScript storage. On reload the app restores the session with a single `/refresh` call, which returns the new access token and the current user, before routing. Connection failures show a retry option without discarding the session.

Refresh tokens in request bodies are not accepted. Sign-in, refresh, and logout require an exact trusted `Origin` header (including API clients). Logout revokes the cookie token and supplied access token before clearing the cookie; a network failure leaves logout available to retry.

Setup: in Google Cloud Console, create an **OAuth client ID** of type *Web application*, add the frontend origins (e.g. `http://localhost`, `http://localhost:5173` and the Vercel URL) under **Authorized JavaScript origins**, and set the same client ID as `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend). The backend checks Google's signature, the audience and the issuer of each ID token. To let anyone outside the test-user list sign in, publish the OAuth app under **Audience**; Google requires the home page and the `/privacy` URL on the **Branding** page first.

Security: Google ID tokens are verified server-side, logout blacklists tokens, and tokens are not persisted in browser storage.

### Phone sign-in (removed)

Settlo used to sign in with SMS codes. Migration `0009` dropped the `otp_codes` table and erased the phone numbers of every account linked to Google. Accounts that never linked Google keep their number only so an admin can confirm the owner before restoring access by hand.

### Restoring access by hand

For someone who cannot reach their old account (never linked Google, or lost their Google account): have them sign in once with the Google account they want to use, which creates an empty Settlo account, and confirm who they are. Then move that Google ID onto their old account in one transaction:

```sql
BEGIN;
-- The empty account their Google sign-in just created. Check it has no groups or friends.
SELECT id, google_sub, email FROM users WHERE email = '<their gmail>';
DELETE FROM users WHERE id = '<empty account id>';
UPDATE users SET google_sub = '<google_sub from above>', email = '<their gmail>'
WHERE id = '<old account id>';
COMMIT;
```

### IDs

Every user picks a unique ID (3-30 letters, numbers, `_` or `.` with at least one letter, case-insensitive, like Instagram). Reserved system names and anything containing `settlo` are refused, and the home page and Settings forms check availability as you type. Signing up does not require one: the home page asks users without an ID to set it (inside the Welcome card for new users, above their groups for existing ones), and anyone can change it in Settings. Friends and group invitations find people by ID.

## Settlement Algorithm

Settlo never moves money; recording a payment only tells Settlo that it happened elsewhere.

Each member's net balance = total paid − total owed. A greedy max-heap matching pairs the largest creditor with the largest debtor repeatedly, settling the group in at most n−1 transactions instead of the naive n². Settlements marked as paid are factored into future calculations.

This is a heuristic, not an optimum: finding the true minimum number of transactions is NP-hard (it reduces to set partition), so there are balance sets a subset-matching pass would settle in fewer transfers. The n−1 bound is a worst case that holds for any input, which is the guarantee worth having here.

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | /api/auth/google | Sign in with a Google ID token, issue tokens |
| POST | /api/auth/set-username | Set display name |
| GET | /api/auth/handle-available | Check whether an ID is free |
| POST | /api/auth/set-handle | Set unique ID (409 if taken or reserved) |
| POST | /api/auth/logout | Blacklist token |
| POST | /api/auth/refresh | New access token and current user |
| GET | /api/auth/me | Current user |
| POST/GET | /api/groups/ | Create / list groups |
| GET/DELETE | /api/groups/{id} | Detail / delete (creator only) |
| GET | /api/groups/{id}/invite | Invite token for the share link |
| GET/POST | /api/groups/join/{token} | Preview / join via invite |
| POST | /api/groups/{id}/members | Add a friend to the group |
| DELETE | /api/groups/{id}/members/{uid} | Remove member / leave group |
| POST/GET | /api/groups/{id}/expenses/ | Create / list expenses |
| PUT | /api/groups/{id}/expenses/{eid} | Edit expense |
| DELETE | /api/groups/{id}/expenses/{eid} | Delete expense |
| GET | /api/groups/{id}/settlements/ | Calculate settlements |
| POST | /api/groups/{id}/settlements/confirm | Archive the group (requires every balance settled) |
| POST | /api/groups/{id}/settlements/{sid}/pay | Record one payment |
| POST | /api/groups/{id}/settlements/{sid}/reverse | Undo a recorded payment |
| GET | /api/groups/{id}/expenses/{eid}/history | Previous versions of an expense |
| POST/GET | /api/group-invitations | Invite by ID / list my pending invites |
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
