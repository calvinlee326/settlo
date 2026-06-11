# Settlo

Split bills among friends for dinners, trips, and more. Settlo calculates who owes whom with the minimum number of transactions.

## Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, SQLite (dev) / PostgreSQL (prod), JWT auth
- **Frontend:** React 18, Vite, Tailwind CSS, React Router v6, Zustand, Axios (PWA-ready)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then change SECRET_KEY
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000 (docs at http://localhost:8000/docs).

Tables are created automatically on first start. To manage schema with Alembic instead:

```bash
alembic upgrade head
```

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

## Authentication

Phone-number login with OTP — no passwords.

1. Enter your phone number on `/login`.
2. A 6-digit OTP is **printed to the backend terminal** (no SMS in development).
3. Enter the code on `/verify`. First-time numbers get an account automatically and are asked for a display name.
4. The app receives a 30-minute access token and a 7-day refresh token; refresh is automatic.

Security: OTP expires in 10 minutes, verification locks for 10 minutes after 5 failed attempts, logout blacklists tokens.

## Settlement Algorithm

Each member's net balance = total paid − total owed. A greedy max-heap matching pairs the largest creditor with the largest debtor repeatedly, producing the minimum number of transactions to settle the group. Settlements marked as paid are factored into future calculations.

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | /api/auth/send-otp | Send (print) OTP |
| POST | /api/auth/verify-otp | Verify OTP, issue tokens |
| POST | /api/auth/set-username | Set display name |
| POST | /api/auth/logout | Blacklist token |
| POST | /api/auth/refresh | New access token |
| GET | /api/auth/me | Current user |
| POST/GET | /api/groups/ | Create / list groups |
| GET/DELETE | /api/groups/{id} | Detail / delete |
| GET | /api/groups/{id}/invite | Invite link |
| GET/POST | /api/groups/join/{token} | Preview / join via invite |
| DELETE | /api/groups/{id}/members/{uid} | Remove member |
| POST/GET | /api/groups/{id}/expenses/ | Create / list expenses |
| DELETE | /api/groups/{id}/expenses/{eid} | Delete expense |
| GET | /api/groups/{id}/settlements/ | Calculate settlements |
| POST | /api/groups/{id}/settlements/{sid}/pay | Mark paid |
