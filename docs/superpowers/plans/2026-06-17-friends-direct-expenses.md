# Friends + Direct Expenses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users connect as friends (mutual request/accept) and split expenses with one or more friends without a group, with per-pair (Splitwise-style) net balances.

**Architecture:** Add a `friendships` table for mutual connections. Reuse the existing `expenses` / `expense_splits` / `settlements` tables for group-less ("direct") expenses by making `group_id` nullable; a direct row has `group_id = NULL`. Friend balances are computed live per pair from direct expenses + direct settlements. The pure helpers in `app/services/settlement.py` are reused unchanged.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (typed `Mapped`) + Alembic (SQLite, batch migrations), Pydantic v2 schemas, `unittest` tests with in-memory SQLite and FastAPI `TestClient`. Frontend: React + Vite + React Router + Zustand + Tailwind (glass utility classes).

## Global Constraints

- Python money values are `Decimal` quantized to `Decimal("0.01")` (`CENT`). Never use float in balance math.
- All API routers are prefixed `/api/...` and every endpoint depends on `get_current_user` (from `app.core.security`).
- New models reuse `generate_uuid` and `utcnow` from `app.models.user`.
- Alembic migrations use `op.batch_alter_table(...)` (SQLite requires batch mode). Latest existing revision is `0002`; new revisions are `0003` then `0004`.
- Single currency for friend netting (default `"USD"`), matching today's group behavior. No multi-currency netting.
- Settlement sign convention (matches `settlements._compute_balances`): for a pair `(me, friend)`, positive balance = friend owes me. A settlement `from_user == me` adds to the balance; `from_user == friend` subtracts.
- Follow existing file patterns: models in `app/models/`, Pydantic schemas in `app/schemas/`, routers in `app/routers/`, reusable logic in `app/services/`.
- Frontend has no test harness; frontend tasks use manual verification steps, not automated tests (matches the repo, which ships no frontend tests).

---

## File Structure

**Backend — create:**
- `backend/app/models/friendship.py` — `Friendship` model + `FriendshipStatus` enum.
- `backend/app/schemas/friend.py` — friend request / friend / direct-expense schemas.
- `backend/app/services/friends.py` — `get_friendship`, `are_friends`, `accepted_friend_ids`, `friend_balance`.
- `backend/app/routers/friends.py` — friend requests, friends list, settle-up, friend expenses.
- `backend/app/routers/direct_expenses.py` — create/delete direct expenses.
- `backend/alembic/versions/0003_friendships.py` — create `friendships` table.
- `backend/alembic/versions/0004_nullable_group_id.py` — make `expenses.group_id` and `settlements.group_id` nullable.
- `backend/tests/test_friendships.py`, `backend/tests/test_direct_expenses.py`.

**Backend — modify:**
- `backend/app/models/__init__.py` — export `Friendship`, `FriendshipStatus`.
- `backend/app/models/expense.py` — `group_id` nullable on `Expense` and `Settlement`.
- `backend/app/schemas/expense.py` — `ExpenseOut.group_id` becomes `str | None`.
- `backend/app/main.py` — register `friends` and `direct_expenses` routers.

**Frontend — create:**
- `frontend/src/pages/FriendsPage.jsx`, `frontend/src/pages/NewDirectExpensePage.jsx`.

**Frontend — modify:**
- `frontend/src/App.jsx` — routes `/friends` and `/friends/expenses/new`.
- `frontend/src/components/Navbar.jsx` — "Friends" link.

---

# Phase 1 — Friendships (backend)

### Task 1: Friendship model + migration

**Files:**
- Create: `backend/app/models/friendship.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0003_friendships.py`
- Test: `backend/tests/test_friendships.py`

**Interfaces:**
- Produces: `FriendshipStatus` (`str` enum: `PENDING`, `ACCEPTED`); `Friendship` model with columns `id, requester_id, addressee_id, status, created_at, responded_at` and unique constraint `uq_friendship_pair` on `(requester_id, addressee_id)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_friendships.py`:

```python
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-friendships")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User


class FriendshipModelTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _users(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.commit()
        return a, b

    def test_friendship_defaults(self):
        a, b = self._users()
        f = Friendship(requester_id=a.id, addressee_id=b.id)
        self.db.add(f)
        self.db.commit()
        reloaded = self.db.query(Friendship).one()
        self.assertEqual(reloaded.status, FriendshipStatus.PENDING)
        self.assertIsNotNone(reloaded.created_at)
        self.assertIsNone(reloaded.responded_at)

    def test_friendship_pair_unique(self):
        a, b = self._users()
        self.db.add(Friendship(requester_id=a.id, addressee_id=b.id))
        self.db.commit()
        self.db.add(Friendship(requester_id=a.id, addressee_id=b.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_friendships.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.friendship'`

- [ ] **Step 3: Create the model**

Create `backend/app/models/friendship.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import generate_uuid, utcnow


class FriendshipStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    addressee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendshipstatus"),
        default=FriendshipStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Export the model**

Edit `backend/app/models/__init__.py` — add the import and `__all__` entries:

```python
from app.models.user import User, OTPCode, TokenBlacklist
from app.models.group import Group, Membership
from app.models.expense import Expense, ExpenseSplit, Settlement, SplitType
from app.models.friendship import Friendship, FriendshipStatus

__all__ = [
    "User",
    "OTPCode",
    "TokenBlacklist",
    "Group",
    "Membership",
    "Expense",
    "ExpenseSplit",
    "Settlement",
    "SplitType",
    "Friendship",
    "FriendshipStatus",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_friendships.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/0003_friendships.py`:

```python
"""friendships table

Revision ID: 0003
Revises: 0002
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("requester_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("addressee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", name="friendshipstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )


def downgrade() -> None:
    op.drop_table("friendships")
```

- [ ] **Step 7: Verify migration applies**

Run: `cd backend && alembic upgrade head && alembic current`
Expected: no error; current shows `0003 (head)`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/friendship.py backend/app/models/__init__.py backend/alembic/versions/0003_friendships.py backend/tests/test_friendships.py
git commit -m "feat: add friendship model and migration"
```

---

### Task 2: Friend schemas + friends service

**Files:**
- Create: `backend/app/schemas/friend.py`
- Create: `backend/app/services/friends.py`
- Test: `backend/tests/test_friendships.py` (add a class)

**Interfaces:**
- Consumes: `Friendship`, `FriendshipStatus` (Task 1); `Expense`, `ExpenseSplit`, `Settlement` (existing).
- Produces:
  - `app/schemas/friend.py`: `FriendRequestCreate{phone_number: str}`, `FriendRequestOut{id, requester_id, requester_username, created_at}`, `FriendOut{id, username, phone_number, net_balance: float}`, `DirectExpenseCreate{title, amount: Decimal, currency, paid_by, split_type, participant_ids: list[str], splits: list[SplitInput] | None}`.
  - `app/services/friends.py`:
    - `get_friendship(db, user_a, user_b) -> Friendship | None` — matches either direction.
    - `are_friends(db, user_a, user_b) -> bool` — True only if an ACCEPTED friendship exists.
    - `accepted_friend_ids(db, user_id) -> set[str]`.
    - `friend_balance(db, user_id, friend_id) -> Decimal` — positive = friend owes user.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_friendships.py` (add imports at top: `from decimal import Decimal`, `from app.models.expense import Expense, ExpenseSplit, Settlement`, `from app.services import friends as friends_svc`, `from app.models.friendship import FriendshipStatus`):

```python
class FriendServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_get_friendship_either_direction(self):
        f = Friendship(requester_id=self.a.id, addressee_id=self.b.id)
        self.db.add(f)
        self.db.commit()
        self.assertIsNotNone(friends_svc.get_friendship(self.db, self.a.id, self.b.id))
        self.assertIsNotNone(friends_svc.get_friendship(self.db, self.b.id, self.a.id))

    def test_are_friends_requires_accepted(self):
        f = Friendship(requester_id=self.a.id, addressee_id=self.b.id)
        self.db.add(f)
        self.db.commit()
        self.assertFalse(friends_svc.are_friends(self.db, self.a.id, self.b.id))
        f.status = FriendshipStatus.ACCEPTED
        self.db.commit()
        self.assertTrue(friends_svc.are_friends(self.db, self.a.id, self.b.id))

    def test_friend_balance_zero_when_no_expenses(self):
        self.assertEqual(
            friends_svc.friend_balance(self.db, self.a.id, self.b.id), Decimal("0.00")
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendServiceTest -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.friends'`

- [ ] **Step 3: Create the schemas**

Create `backend/app/schemas/friend.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.expense import SplitType
from app.schemas.expense import SplitInput


class FriendRequestCreate(BaseModel):
    phone_number: str = Field(min_length=3, max_length=20)


class FriendRequestOut(BaseModel):
    id: str
    requester_id: str
    requester_username: str | None
    created_at: datetime


class FriendOut(BaseModel):
    id: str
    username: str | None
    phone_number: str
    net_balance: float


class DirectExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    paid_by: str
    split_type: SplitType = SplitType.EQUAL
    participant_ids: list[str] = Field(min_length=2)
    splits: list[SplitInput] | None = None
```

- [ ] **Step 4: Create the service**

Create `backend/app/services/friends.py`:

```python
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.friendship import Friendship, FriendshipStatus

CENT = Decimal("0.01")


def get_friendship(db: Session, user_a: str, user_b: str) -> Friendship | None:
    return (
        db.query(Friendship)
        .filter(
            or_(
                and_(
                    Friendship.requester_id == user_a,
                    Friendship.addressee_id == user_b,
                ),
                and_(
                    Friendship.requester_id == user_b,
                    Friendship.addressee_id == user_a,
                ),
            )
        )
        .first()
    )


def are_friends(db: Session, user_a: str, user_b: str) -> bool:
    f = get_friendship(db, user_a, user_b)
    return f is not None and f.status == FriendshipStatus.ACCEPTED


def accepted_friend_ids(db: Session, user_id: str) -> set[str]:
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
        .all()
    )
    ids: set[str] = set()
    for f in rows:
        ids.add(f.addressee_id if f.requester_id == user_id else f.requester_id)
    return ids


def friend_balance(db: Session, user_id: str, friend_id: str) -> Decimal:
    """Net for the (user_id, friend_id) pair across direct rows.

    Positive = friend owes user_id.
    """
    bal = Decimal("0")

    # Direct expenses user paid -> friend's share is owed to user.
    paid_by_user = (
        db.query(ExpenseSplit.amount)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by == user_id,
            ExpenseSplit.user_id == friend_id,
        )
        .all()
    )
    for (amount,) in paid_by_user:
        bal += Decimal(amount)

    # Direct expenses friend paid -> user's share is owed to friend.
    paid_by_friend = (
        db.query(ExpenseSplit.amount)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by == friend_id,
            ExpenseSplit.user_id == user_id,
        )
        .all()
    )
    for (amount,) in paid_by_friend:
        bal -= Decimal(amount)

    # Direct settlements between the pair (same sign rule as group balances).
    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.group_id.is_(None),
            Settlement.is_paid.is_(True),
            or_(
                and_(
                    Settlement.from_user == user_id,
                    Settlement.to_user == friend_id,
                ),
                and_(
                    Settlement.from_user == friend_id,
                    Settlement.to_user == user_id,
                ),
            ),
        )
        .all()
    )
    for s in settlements:
        if s.from_user == user_id:
            bal += Decimal(s.amount)
        else:
            bal -= Decimal(s.amount)

    return bal.quantize(CENT)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendServiceTest -v`
Expected: PASS (3 tests). `friend_balance` returns `Decimal("0.00")` because no direct rows exist yet (queries tolerate the not-yet-nullable column — no NULL rows exist).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/friend.py backend/app/services/friends.py backend/tests/test_friendships.py
git commit -m "feat: add friend schemas and friends service with balance helper"
```

---

### Task 3: Friend request endpoints

**Files:**
- Create: `backend/app/routers/friends.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_friendships.py` (add a `TestClient` class)

**Interfaces:**
- Consumes: `friends_svc.get_friendship` (Task 2); `FriendRequestCreate`, `FriendRequestOut` (Task 2); `get_current_user` (existing).
- Produces router `friends.router` with prefix `/api/friends`:
  - `POST /api/friends/requests` `{phone_number}` -> 201 `FriendRequestOut`.
  - `GET /api/friends/requests` -> `list[FriendRequestOut]` (incoming PENDING).
  - `POST /api/friends/requests/{friendship_id}/accept` -> 204.
  - `POST /api/friends/requests/{friendship_id}/decline` -> 204.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_friendships.py`. Add these imports at the top of the file:

```python
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
```

Add the class:

```python
class FriendRequestApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def test_send_request_creates_pending(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            self.db.query(Friendship).count(), 1
        )

    def test_cannot_friend_self(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.a.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_duplicate_request_rejected(self):
        self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_unknown_phone_404(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": "+15559999999"},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 404)

    def test_incoming_requests_and_accept(self):
        self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        incoming = self.client.get(
            "/api/friends/requests", headers=self._auth(self.b)
        ).json()
        self.assertEqual(len(incoming), 1)
        fid = incoming[0]["id"]
        res = self.client.post(
            f"/api/friends/requests/{fid}/accept", headers=self._auth(self.b)
        )
        self.assertEqual(res.status_code, 204)
        f = self.db.query(Friendship).one()
        self.db.refresh(f)
        self.assertEqual(f.status, FriendshipStatus.ACCEPTED)

    def test_decline_deletes_request(self):
        self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        fid = self.db.query(Friendship).one().id
        res = self.client.post(
            f"/api/friends/requests/{fid}/decline", headers=self._auth(self.b)
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.db.query(Friendship).count(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendRequestApiTest -v`
Expected: FAIL — 404s on `/api/friends/requests` (router not registered).

- [ ] **Step 3: Create the router**

Create `backend/app/routers/friends.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User, utcnow
from app.schemas.friend import FriendRequestCreate, FriendRequestOut
from app.services import friends as friends_svc

router = APIRouter(prefix="/api/friends", tags=["friends"])


@router.post(
    "/requests", response_model=FriendRequestOut, status_code=status.HTTP_201_CREATED
)
def send_friend_request(
    body: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = (
        db.query(User).filter(User.phone_number == body.phone_number).first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that phone number"
        )
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot add yourself",
        )
    if friends_svc.get_friendship(db, current_user.id, target.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A friend request already exists",
        )

    friendship = Friendship(requester_id=current_user.id, addressee_id=target.id)
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return FriendRequestOut(
        id=friendship.id,
        requester_id=friendship.requester_id,
        requester_username=current_user.username,
        created_at=friendship.created_at,
    )


@router.get("/requests", response_model=list[FriendRequestOut])
def incoming_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .order_by(Friendship.created_at.desc())
        .all()
    )
    requesters = {
        u.id: u.username
        for u in db.query(User)
        .filter(User.id.in_([f.requester_id for f in rows]))
        .all()
    } if rows else {}
    return [
        FriendRequestOut(
            id=f.id,
            requester_id=f.requester_id,
            requester_username=requesters.get(f.requester_id),
            created_at=f.created_at,
        )
        for f in rows
    ]


def _get_incoming_or_404(db: Session, friendship_id: str, user_id: str) -> Friendship:
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.id == friendship_id,
            Friendship.addressee_id == user_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .first()
    )
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    return friendship


@router.post("/requests/{friendship_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    friendship.status = FriendshipStatus.ACCEPTED
    friendship.responded_at = utcnow()
    db.commit()


@router.post("/requests/{friendship_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    db.delete(friendship)
    db.commit()
```

- [ ] **Step 4: Register the router**

Edit `backend/app/main.py`:
- Change the import line `from app.routers import auth, expenses, groups, settlements` to `from app.routers import auth, expenses, friends, groups, settlements`.
- After `app.include_router(settlements.router)` add `app.include_router(friends.router)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendRequestApiTest -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/friends.py backend/app/main.py backend/tests/test_friendships.py
git commit -m "feat: add friend request endpoints"
```

---

### Task 4: Friends list + remove friend

**Files:**
- Modify: `backend/app/routers/friends.py`
- Test: `backend/tests/test_friendships.py` (extend `FriendRequestApiTest` or add a class)

**Interfaces:**
- Consumes: `friends_svc.friend_balance`, `friends_svc.accepted_friend_ids` (Task 2); `FriendOut` (Task 2).
- Produces:
  - `GET /api/friends` -> `list[FriendOut]` (accepted friends with `net_balance`).
  - `DELETE /api/friends/{friend_id}` -> 204; 400 if `friend_balance != 0`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_friendships.py`:

```python
class FriendListApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
        self.db.add(
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.b.id,
                status=FriendshipStatus.ACCEPTED,
            )
        )
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def test_list_friends(self):
        res = self.client.get("/api/friends", headers=self._auth(self.a))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.b.id)
        self.assertEqual(data[0]["net_balance"], 0.0)

    def test_remove_friend_when_settled(self):
        res = self.client.delete(
            f"/api/friends/{self.b.id}", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.db.query(Friendship).count(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendListApiTest -v`
Expected: FAIL — 405/404 on `GET /api/friends` and `DELETE`.

- [ ] **Step 3: Add the endpoints**

In `backend/app/routers/friends.py`, add to the imports:

```python
from app.schemas.friend import FriendOut, FriendRequestCreate, FriendRequestOut
```

(replace the existing `from app.schemas.friend import FriendRequestCreate, FriendRequestOut` line) and append:

```python
@router.get("", response_model=list[FriendOut])
def list_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friend_ids = friends_svc.accepted_friend_ids(db, current_user.id)
    if not friend_ids:
        return []
    users = db.query(User).filter(User.id.in_(friend_ids)).all()
    return [
        FriendOut(
            id=u.id,
            username=u.username,
            phone_number=u.phone_number,
            net_balance=float(friends_svc.friend_balance(db, current_user.id, u.id)),
        )
        for u in users
    ]


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = friends_svc.get_friendship(db, current_user.id, friend_id)
    if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    if friends_svc.friend_balance(db, current_user.id, friend_id) != Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Settle the balance before removing this friend",
        )
    db.delete(friendship)
    db.commit()
```

Also add `from decimal import Decimal` to the imports at the top of `friends.py`.

> Note: `GET /api/friends` is registered with path `""` (so the full path is `/api/friends`). Keep it declared after the `/requests` routes are fine; FastAPI matches the literal `/requests` paths before the `/{friend_id}` parameter route regardless of order.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_friendships.py::FriendListApiTest -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the whole friendships suite**

Run: `cd backend && python -m pytest tests/test_friendships.py -v`
Expected: PASS (all classes)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/friends.py backend/tests/test_friendships.py
git commit -m "feat: add friends list and remove-friend endpoints"
```

---

# Phase 2 — Direct expenses + balances (backend)

### Task 5: Make `group_id` nullable

**Files:**
- Modify: `backend/app/models/expense.py:21` (Expense.group_id) and `:54` (Settlement.group_id)
- Modify: `backend/app/schemas/expense.py` (`ExpenseOut.group_id`)
- Create: `backend/alembic/versions/0004_nullable_group_id.py`
- Test: `backend/tests/test_direct_expenses.py`

**Interfaces:**
- Produces: `Expense.group_id` and `Settlement.group_id` typed `Mapped[str | None]`, nullable; `ExpenseOut.group_id: str | None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_direct_expenses.py`:

```python
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-direct-expenses")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit
from app.models.user import User


class NullableGroupIdTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_expense_allows_null_group(self):
        u = User(phone_number="+15550000001", username="A")
        self.db.add(u)
        self.db.flush()
        e = Expense(
            group_id=None,
            paid_by=u.id,
            title="Coffee",
            amount=Decimal("4.00"),
            created_by=u.id,
        )
        self.db.add(e)
        self.db.commit()
        self.assertIsNone(self.db.query(Expense).one().group_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::NullableGroupIdTest -v`
Expected: FAIL — `IntegrityError: NOT NULL constraint failed: expenses.group_id`

- [ ] **Step 3: Make the model columns nullable**

In `backend/app/models/expense.py`:

Change Expense (line ~21):
```python
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id"), nullable=True
    )
```

Change Settlement (line ~54):
```python
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id"), nullable=True
    )
```

- [ ] **Step 4: Make `ExpenseOut.group_id` optional**

In `backend/app/schemas/expense.py`, change `group_id: str` to `group_id: str | None` in `ExpenseOut`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::NullableGroupIdTest -v`
Expected: PASS

- [ ] **Step 6: Create the migration**

Create `backend/alembic/versions/0004_nullable_group_id.py`:

```python
"""make expense and settlement group_id nullable

Revision ID: 0004
Revises: 0003
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=True)
    with op.batch_alter_table("settlements", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("settlements", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("group_id", existing_type=sa.String(36), nullable=False)
```

- [ ] **Step 7: Verify migration applies**

Run: `cd backend && alembic upgrade head && alembic current`
Expected: current shows `0004 (head)`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/expense.py backend/app/schemas/expense.py backend/alembic/versions/0004_nullable_group_id.py backend/tests/test_direct_expenses.py
git commit -m "feat: make expense and settlement group_id nullable for direct expenses"
```

---

### Task 6: Direct expense create / list / delete

**Files:**
- Create: `backend/app/routers/direct_expenses.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/friends.py` (add `GET /api/friends/{friend_id}/expenses`)
- Test: `backend/tests/test_direct_expenses.py` (add a `TestClient` class)

**Interfaces:**
- Consumes: `_build_splits`, `_expense_out` from `app.routers.expenses` (existing, importable); `DirectExpenseCreate` (Task 2); `friends_svc.are_friends` (Task 2); `ExpenseOut` (existing).
- Produces router `direct_expenses.router` with prefix `/api/direct-expenses`:
  - `POST /api/direct-expenses` `DirectExpenseCreate` -> 201 `ExpenseOut` (with `group_id == None`).
  - `DELETE /api/direct-expenses/{expense_id}` -> 204 (creator only).
- Also adds to `friends.router`: `GET /api/friends/{friend_id}/expenses` -> `list[ExpenseOut]`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_direct_expenses.py`. Add these imports near the top:

```python
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.models.friendship import Friendship, FriendshipStatus
```

Add the class:

```python
class DirectExpenseApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.c = User(phone_number="+15550000003", username="C")
        self.db.add_all([self.a, self.b, self.c])
        self.db.add_all([
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.b.id,
                status=FriendshipStatus.ACCEPTED,
            ),
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.c.id,
                status=FriendshipStatus.ACCEPTED,
            ),
        ])
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def test_create_equal_direct_expense(self):
        res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "30.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id, self.c.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertIsNone(body["group_id"])
        self.assertEqual(len(body["splits"]), 3)

    def test_reject_non_friend_participant(self):
        stranger = User(phone_number="+15550000009", username="Z")
        self.db.add(stranger)
        self.db.commit()
        res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "10.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, stranger.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 403)

    def test_friend_expenses_listing(self):
        self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "20.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id],
            },
            headers=self._auth(self.a),
        )
        res = self.client.get(
            f"/api/friends/{self.b.id}/expenses", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::DirectExpenseApiTest -v`
Expected: FAIL — 404 on `/api/direct-expenses` (router not registered).

- [ ] **Step 3: Create the direct-expenses router**

Create `backend/app/routers/direct_expenses.py`:

```python
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit
from app.models.user import User
from app.routers.expenses import _build_splits, _expense_out
from app.schemas.expense import ExpenseOut
from app.schemas.friend import DirectExpenseCreate
from app.services import friends as friends_svc

router = APIRouter(prefix="/api/direct-expenses", tags=["direct-expenses"])

CENT = Decimal("0.01")


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_direct_expense(
    body: DirectExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participants = set(body.participant_ids) | {body.paid_by}
    others = participants - {current_user.id}
    for uid in others:
        if not friends_svc.are_friends(db, current_user.id, uid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="All participants must be your friends",
            )
    if body.paid_by not in participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payer must be a participant",
        )

    member_ids = list(participants)
    splits = _build_splits(body, member_ids)

    expense = Expense(
        group_id=None,
        paid_by=body.paid_by,
        title=body.title.strip(),
        amount=body.amount.quantize(CENT),
        currency=body.currency.upper(),
        split_type=body.split_type,
        created_by=current_user.id,
    )
    db.add(expense)
    db.flush()
    for user_id, amount in splits:
        db.add(ExpenseSplit(expense_id=expense.id, user_id=user_id, amount=amount))
    db.commit()
    db.refresh(expense)
    return _expense_out(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_direct_expense(
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.group_id.is_(None))
        .first()
    )
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )
    if expense.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can delete this expense",
        )
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).delete(
        synchronize_session=False
    )
    db.delete(expense)
    db.commit()
```

> Note on `_build_splits`: it reads only `body.amount`, `body.split_type`, and `body.splits`, and checks split user_ids against `member_ids`. `DirectExpenseCreate` supplies all three, so it works unchanged. For EQUAL splits, `member_ids` (the participant set) defines who shares.

- [ ] **Step 4: Add the friend-expenses listing endpoint**

In `backend/app/routers/friends.py`, add imports:

```python
from sqlalchemy.orm import Session, joinedload
from app.models.expense import Expense, ExpenseSplit
from app.routers.expenses import _expense_out
from app.schemas.expense import ExpenseOut
```

(merge the `Session` import with the existing `from sqlalchemy.orm import Session` line) and append:

```python
@router.get("/{friend_id}/expenses", response_model=list[ExpenseOut])
def friend_expenses(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not friends_svc.are_friends(db, current_user.id, friend_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    # Direct expenses where both the caller and the friend appear in the splits.
    pair_expense_ids = (
        db.query(ExpenseSplit.expense_id)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(Expense.group_id.is_(None))
        .filter(ExpenseSplit.user_id.in_([current_user.id, friend_id]))
        .group_by(ExpenseSplit.expense_id)
        .having(func.count(func.distinct(ExpenseSplit.user_id)) == 2)
        .all()
    )
    ids = [row[0] for row in pair_expense_ids]
    if not ids:
        return []
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits).joinedload(ExpenseSplit.user))
        .options(joinedload(Expense.payer))
        .filter(Expense.id.in_(ids))
        .order_by(Expense.created_at.desc())
        .all()
    )
    return [_expense_out(e) for e in expenses]
```

Add `from sqlalchemy import func` to the imports at the top of `friends.py`.

- [ ] **Step 5: Register the direct-expenses router**

Edit `backend/app/main.py`:
- Add `direct_expenses` to the routers import: `from app.routers import auth, direct_expenses, expenses, friends, groups, settlements`.
- After `app.include_router(friends.router)` add `app.include_router(direct_expenses.router)`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::DirectExpenseApiTest -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/direct_expenses.py backend/app/routers/friends.py backend/app/main.py backend/tests/test_direct_expenses.py
git commit -m "feat: add direct expense create/delete and friend expense listing"
```

---

### Task 7: Friend balance with real data + settle-up

**Files:**
- Modify: `backend/app/routers/friends.py` (add `POST /api/friends/{friend_id}/settle`)
- Test: `backend/tests/test_direct_expenses.py` (add a class)

**Interfaces:**
- Consumes: `friends_svc.friend_balance` (Task 2); `Settlement` (existing).
- Produces: `POST /api/friends/{friend_id}/settle` -> 200 `{settled_amount: float}`; records a paid `Settlement` with `group_id == None` that zeroes the pair balance. No-op (400) when balance is 0.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_direct_expenses.py`:

```python
class FriendSettleTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.c = User(phone_number="+15550000003", username="C")
        self.db.add_all([self.a, self.b, self.c])
        self.db.add_all([
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.b.id,
                status=FriendshipStatus.ACCEPTED,
            ),
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.c.id,
                status=FriendshipStatus.ACCEPTED,
            ),
        ])
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def test_three_person_balance_and_settle(self):
        # A pays 30 split equally among A, B, C -> B owes A 10, C owes A 10.
        self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "30.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id, self.c.id],
            },
            headers=self._auth(self.a),
        )
        friends = {
            f["id"]: f["net_balance"]
            for f in self.client.get(
                "/api/friends", headers=self._auth(self.a)
            ).json()
        }
        self.assertEqual(friends[self.b.id], 10.0)
        self.assertEqual(friends[self.c.id], 10.0)

        # B's view: B owes A 10 -> negative.
        b_friends = {
            f["id"]: f["net_balance"]
            for f in self.client.get(
                "/api/friends", headers=self._auth(self.b)
            ).json()
        }
        self.assertEqual(b_friends[self.a.id], -10.0)

        # A settles up with B.
        res = self.client.post(
            f"/api/friends/{self.b.id}/settle", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 200)
        friends_after = {
            f["id"]: f["net_balance"]
            for f in self.client.get(
                "/api/friends", headers=self._auth(self.a)
            ).json()
        }
        self.assertEqual(friends_after[self.b.id], 0.0)
        self.assertEqual(friends_after[self.c.id], 10.0)

    def test_settle_zero_balance_rejected(self):
        res = self.client.post(
            f"/api/friends/{self.b.id}/settle", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::FriendSettleTest -v`
Expected: FAIL — 404/405 on `POST /api/friends/{id}/settle`.

- [ ] **Step 3: Add the settle endpoint**

In `backend/app/routers/friends.py`, add to imports:

```python
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.user import User, utcnow
```

(merge with the existing `from app.models.user import User, utcnow` and `from app.models.expense ...` lines) and append:

```python
@router.post("/{friend_id}/settle")
def settle_with_friend(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not friends_svc.are_friends(db, current_user.id, friend_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    balance = friends_svc.friend_balance(db, current_user.id, friend_id)
    if balance == Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to settle",
        )
    # Positive balance: friend owes me -> friend pays me (from=friend, to=me).
    # Negative balance: I owe friend -> I pay friend (from=me, to=friend).
    if balance > 0:
        from_user, to_user, amount = friend_id, current_user.id, balance
    else:
        from_user, to_user, amount = current_user.id, friend_id, -balance
    db.add(
        Settlement(
            group_id=None,
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            is_paid=True,
            paid_at=utcnow(),
        )
    )
    db.commit()
    return {"settled_amount": float(amount)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_direct_expenses.py::FriendSettleTest -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/friends.py backend/tests/test_direct_expenses.py
git commit -m "feat: add friend settle-up and verify per-pair balance math"
```

---

# Phase 3 — Frontend

> Frontend has no automated test harness. Each task ends with manual verification against a running stack (`docker-compose up` or backend `uvicorn app.main:app` + frontend `npm run dev`). Use two test accounts (two phone numbers; DEV_OTP_CODE bypass works for local login).

### Task 8: Friends page (list, requests, add)

**Files:**
- Create: `frontend/src/pages/FriendsPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Navbar.jsx`

**Interfaces:**
- Consumes backend: `GET/POST /api/friends/requests`, `POST /api/friends/requests/{id}/accept|decline`, `GET /api/friends`, `DELETE /api/friends/{id}`, `POST /api/friends/{id}/settle`.

- [ ] **Step 1: Create the FriendsPage**

Create `frontend/src/pages/FriendsPage.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';

export default function FriendsPage() {
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () =>
    Promise.all([api.get('/friends'), api.get('/friends/requests')])
      .then(([f, r]) => {
        setFriends(f.data);
        setRequests(r.data);
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load friends')
      )
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const addFriend = async () => {
    setError('');
    setNotice('');
    const val = phone.trim();
    if (!val) return;
    try {
      await api.post('/friends/requests', { phone_number: val });
      setPhone('');
      setNotice('Request sent');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send request');
    }
  };

  const respond = async (id, action) => {
    setError('');
    try {
      await api.post(`/friends/requests/${id}/${action}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update request');
    }
  };

  const settle = async (friendId) => {
    setError('');
    try {
      await api.post(`/friends/${friendId}/settle`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to settle');
    }
  };

  const remove = async (friendId) => {
    setError('');
    try {
      await api.delete(`/friends/${friendId}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove friend');
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">Friends</h1>
      <ErrorMessage message={error} />
      {notice && <p className="text-sm text-emerald-400">{notice}</p>}

      <div className="glass space-y-3 p-4">
        <p className="text-[13px] font-medium text-white/55">Add a friend</p>
        <div className="flex gap-2">
          <input
            type="tel"
            placeholder="Phone number e.g. +15550000002"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addFriend()}
            className="min-w-0 flex-1 rounded-xl bg-white/10 px-3 py-2 text-[14px] text-white placeholder-white/30 outline-none"
          />
          <button
            onClick={addFriend}
            disabled={!phone.trim()}
            className="shrink-0 rounded-xl bg-violet-500 px-4 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>

      {requests.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-white/90">Requests</h2>
          {requests.map((r) => (
            <div
              key={r.id}
              className="glass flex items-center justify-between p-4"
            >
              <span className="text-[15px] text-white/85">
                {r.requester_username || 'Someone'}
              </span>
              <div className="flex gap-2">
                <Button variant="accent" onClick={() => respond(r.id, 'accept')}>
                  Accept
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => respond(r.id, 'decline')}
                >
                  Decline
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-lg font-medium text-white/90">Your friends</h2>
        {friends.length === 0 ? (
          <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
            <p className="text-[15px] text-white/55">No friends yet.</p>
          </div>
        ) : (
          friends.map((f) => (
            <div
              key={f.id}
              className="glass flex items-center justify-between p-4"
            >
              <div>
                <p className="text-[15px] font-medium text-white/85">
                  {f.username || f.phone_number}
                </p>
                <p
                  className={`text-sm tabular-nums ${
                    f.net_balance > 0
                      ? 'text-emerald-400'
                      : f.net_balance < 0
                        ? 'text-red-400'
                        : 'text-white/45'
                  }`}
                >
                  {f.net_balance > 0
                    ? `owes you $${f.net_balance.toFixed(2)}`
                    : f.net_balance < 0
                      ? `you owe $${Math.abs(f.net_balance).toFixed(2)}`
                      : 'settled up'}
                </p>
              </div>
              <div className="flex gap-2">
                {f.net_balance !== 0 ? (
                  <Button variant="accent" onClick={() => settle(f.id)}>
                    Settle
                  </Button>
                ) : (
                  <Button variant="secondary" onClick={() => remove(f.id)}>
                    Remove
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <Link
        to="/friends/expenses/new"
        aria-label="Add friend expense"
        className="fab"
      >
        +
      </Link>
    </div>
  );
}
```

- [ ] **Step 2: Add the route**

In `frontend/src/App.jsx`:
- Add `import FriendsPage from './pages/FriendsPage';` with the other page imports.
- Add this route block alongside the others (inside `<Routes>`):

```jsx
      <Route
        path="/friends"
        element={
          <ProtectedRoute>
            <Layout>
              <FriendsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
```

- [ ] **Step 3: Add the Navbar link**

In `frontend/src/components/Navbar.jsx`, inside the right-hand `<div className="flex items-center gap-3">`, before the user block, add:

```jsx
          <Link
            to="/friends"
            className="text-sm font-medium text-white/55 transition-colors hover:text-white"
          >
            Friends
          </Link>
```

(`Link` is already imported in Navbar.jsx.)

- [ ] **Step 4: Manual verification**

Start the stack. Log in as user A. Go to `/friends`:
- Add user B by phone -> "Request sent".
- Log in as B (second browser/incognito) -> see request -> Accept.
- Back as A -> B appears under "Your friends" with "settled up".

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/FriendsPage.jsx frontend/src/App.jsx frontend/src/components/Navbar.jsx
git commit -m "feat: add friends page with requests, balances, and settle-up"
```

---

### Task 9: New direct expense page

**Files:**
- Create: `frontend/src/pages/NewDirectExpensePage.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes backend: `GET /api/friends`, `POST /api/direct-expenses`.

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/NewDirectExpensePage.jsx`:

```jsx
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import useAuthStore from '../store/authStore';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';

export default function NewDirectExpensePage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [friends, setFriends] = useState([]);
  const [selected, setSelected] = useState({});
  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState('');
  const [paidBy, setPaidBy] = useState(user?.id || '');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get('/friends')
      .then(({ data }) => setFriends(data))
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load friends')
      )
      .finally(() => setLoading(false));
  }, []);

  // Participants = me + selected friends.
  const participantIds = useMemo(() => {
    const ids = [user?.id].filter(Boolean);
    friends.forEach((f) => {
      if (selected[f.id]) ids.push(f.id);
    });
    return ids;
  }, [friends, selected, user]);

  const totalAmount = parseFloat(amount) || 0;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    if (!(totalAmount > 0)) {
      setError('Amount must be greater than 0');
      return;
    }
    if (participantIds.length < 2) {
      setError('Pick at least one friend');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/direct-expenses', {
        title: title.trim(),
        amount: totalAmount.toFixed(2),
        paid_by: paidBy,
        split_type: 'EQUAL',
        participant_ids: participantIds,
      });
      navigate('/friends');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add expense');
      setSubmitting(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  const payerOptions = friends.filter((f) => selected[f.id]);

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-white">Friend Expense</h1>
      <form onSubmit={handleSubmit} className="glass space-y-4 p-6">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Title
          </label>
          <input
            type="text"
            placeholder="e.g. Dinner"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="input-glass"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Amount
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/35">
              $
            </span>
            <input
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="input-glass pl-8"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Split with
          </label>
          <div className="space-y-2 rounded-[14px] border border-white/10 bg-white/[0.04] p-4">
            {friends.length === 0 && (
              <p className="text-sm text-white/45">
                Add friends first to split with them.
              </p>
            )}
            {friends.map((f) => (
              <label
                key={f.id}
                className="flex cursor-pointer items-center gap-3 text-[15px] text-white/75"
              >
                <input
                  type="checkbox"
                  checked={!!selected[f.id]}
                  onChange={(e) =>
                    setSelected((prev) => ({
                      ...prev,
                      [f.id]: e.target.checked,
                    }))
                  }
                />
                {f.username || f.phone_number}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-white/50">
            Paid by
          </label>
          <select
            value={paidBy}
            onChange={(e) => setPaidBy(e.target.value)}
            className="input-glass"
          >
            <option value={user?.id}>You</option>
            {payerOptions.map((f) => (
              <option key={f.id} value={f.id}>
                {f.username || f.phone_number}
              </option>
            ))}
          </select>
        </div>

        <ErrorMessage message={error} />
        <div className="flex gap-3">
          <Button
            type="button"
            variant="secondary"
            className="flex-1"
            onClick={() => navigate('/friends')}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="accent"
            disabled={submitting}
            className="flex-1"
          >
            {submitting ? 'Saving…' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </div>
  );
}
```

> Note: EQUAL split only (matches the "lazy" scope). If `paidBy` points to a friend who is later deselected, the backend rejects it (payer must be a participant) and the error surfaces; the payer dropdown only lists selected friends + You.

- [ ] **Step 2: Add the route**

In `frontend/src/App.jsx`:
- Add `import NewDirectExpensePage from './pages/NewDirectExpensePage';`.
- Add the route:

```jsx
      <Route
        path="/friends/expenses/new"
        element={
          <ProtectedRoute>
            <Layout>
              <NewDirectExpensePage />
            </Layout>
          </ProtectedRoute>
        }
      />
```

- [ ] **Step 3: Manual verification**

As user A (friends with B and C): `/friends` -> tap `+` -> create "Dinner" $30 paid by You, split with B and C.
- Back on `/friends`: B owes you $10.00, C owes you $10.00.
- Tap Settle on B -> B becomes "settled up"; C still owes $10.00.
- Log in as B -> `/friends` shows "settled up" with A.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NewDirectExpensePage.jsx frontend/src/App.jsx
git commit -m "feat: add new direct (friend) expense page"
```

---

## Final verification

- [ ] Run full backend suite: `cd backend && python -m pytest -v` — all pass.
- [ ] Confirm migrations apply cleanly from scratch: delete a throwaway DB and `alembic upgrade head` -> `0004 (head)`.
- [ ] Manual end-to-end: two accounts, request/accept, multi-person direct expense, per-pair balances, settle-up, remove friend.

## Notes for the implementer

- `_build_splits` and `_expense_out` live in `app/routers/expenses.py` and are imported by the direct-expenses router — do not duplicate that logic.
- The settlement sign convention is the single source of truth in `friend_balance`; keep it consistent with `settlements._compute_balances`.
- Direct expenses never set `group_id`; group expense flows are untouched. Group balance math (`settlements._compute_balances` filters by a concrete `group_id`) is unaffected by NULL-group rows.
