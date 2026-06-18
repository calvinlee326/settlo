# Better Group Joining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four better ways to join a group — invite friends directly, short join code, QR code, invite by phone — keeping the existing invite link as a fallback.

**Architecture:** Extract the member-add + EQUAL-re-split logic into one `_add_member` helper reused by every join path. Short codes replace token generation. A new `GroupInvitation` model (mirroring `Friendship`) powers phone invites. Frontend reuses the existing phone normalization and Navbar badge patterns.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic (SQLite, batch migrations), Pydantic v2, `unittest` + FastAPI `TestClient` (in-memory SQLite with `StaticPool`). Frontend: React + Vite + React Router + Zustand + Tailwind; new dep `qrcode.react`.

## Global Constraints

- All routers `/api/...`; every endpoint depends on `get_current_user` (`app.core.security`).
- Money: EQUAL re-split uses the existing `equal_split` from `app.services.settlement` (Decimal quantized to `CENT`). Never reimplement split math.
- `_add_member(db, group, user_id)` is the ONLY place that creates a group `Membership` for a join; it enforces idempotency, settled-block, capacity, and re-split.
- Default-deny: add-member requires an accepted friendship; invite-create requires caller membership; accept/decline are addressee-only.
- Phone numbers are stored/compared as `+1XXXXXXXXXX`; the frontend normalizes any input to that form (mirror `LoginPage`/`FriendsPage`: strip non-digits, drop a leading `1` on 11 digits, require 10, send `+1${digits}`).
- TestClient + in-memory SQLite setUp MUST use `poolclass=StaticPool` and `db.flush()` before constructing rows that reference auto-generated IDs (see `tests/test_friendships.py` for the pattern).
- Alembic: batch mode for SQLite; latest revision is `0004`; new revision is `0005`.
- Short-code alphabet: `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no `0/O/1/I/L`), length 6.
- Frontend gate is `npm run build` (no frontend test harness); manual click-through is separate.

---

## File Structure

**Backend — create:**
- `backend/app/models/group_invitation.py` — `GroupInvitation` + `GroupInvitationStatus`.
- `backend/app/routers/group_invitations.py` — phone-invite endpoints.
- `backend/alembic/versions/0005_group_invitations.py`.
- `backend/tests/test_group_join.py`, `backend/tests/test_group_invitations.py`.

**Backend — modify:**
- `backend/app/routers/groups.py` — `_add_member`, refactor `join_group`, short-code helpers, `add_member` endpoint.
- `backend/app/schemas/group.py` — `AddMemberRequest`, `GroupInviteCreate`, `GroupInvitationOut`.
- `backend/app/models/__init__.py` — export `GroupInvitation`, `GroupInvitationStatus`.
- `backend/app/main.py` — register `group_invitations` router.

**Frontend — modify:**
- `frontend/src/pages/GroupDetailPage.jsx` — code + QR, add-friends, invite-by-phone.
- `frontend/src/pages/HomePage.jsx` — pending group invites.
- `frontend/src/components/Navbar.jsx` — group-invite badge on the home link.
- `frontend/package.json` — `qrcode.react`.

---

# Phase A — Refactor + cheap wins

### Task 1: Extract `_add_member`, refactor `join_group`, block settled joins

**Files:**
- Modify: `backend/app/routers/groups.py`
- Test: `backend/tests/test_group_join.py` (new)

**Interfaces:**
- Produces `_add_member(db: Session, group: Group, user_id: str) -> None` in `groups.py`. Idempotent; raises 400 on settled or full; adds `Membership`; re-splits EQUAL expenses.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_group_join.py`:

```python
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-group-join")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.group import Group, Membership
from app.models.user import User, utcnow


class GroupJoinTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()
        self.owner = User(phone_number="+15550000001", username="Owner")
        self.joiner = User(phone_number="+15550000002", username="Joiner")
        self.db.add_all([self.owner, self.joiner])
        self.db.flush()
        self.group = Group(name="Trip", created_by=self.owner.id, invite_token="ABCDEF")
        self.db.add(self.group)
        self.db.flush()
        self.db.add(Membership(user_id=self.owner.id, group_id=self.group.id))
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

    def test_join_via_code_adds_member(self):
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.joiner)
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_join_settled_group_blocked(self):
        with self.Session() as s:
            g = s.query(Group).filter(Group.id == self.group.id).one()
            g.settled_at = utcnow()
            s.commit()
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.joiner)
        )
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_group_join.py -v`
Expected: `test_join_settled_group_blocked` FAILS (currently joining a settled group succeeds with 200).

- [ ] **Step 3: Add `_add_member` and refactor `join_group`**

In `backend/app/routers/groups.py`, add this helper (place it after `require_membership`):

```python
def _add_member(db: Session, group: Group, user_id: str) -> None:
    existing = (
        db.query(Membership)
        .filter(Membership.group_id == group.id, Membership.user_id == user_id)
        .first()
    )
    if existing:
        return
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    member_count = (
        db.query(Membership).filter(Membership.group_id == group.id).count()
    )
    if member_count >= group.max_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is full"
        )
    db.add(Membership(user_id=user_id, group_id=group.id))
    db.flush()
    member_ids = [
        m.user_id
        for m in db.query(Membership).filter(Membership.group_id == group.id).all()
    ]
    equal_expenses = (
        db.query(Expense)
        .filter(Expense.group_id == group.id, Expense.split_type == SplitType.EQUAL)
        .all()
    )
    for e in equal_expenses:
        db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == e.id).delete(
            synchronize_session=False
        )
        for uid, amount in equal_split(Decimal(e.amount), member_ids):
            db.add(ExpenseSplit(expense_id=e.id, user_id=uid, amount=amount))
```

Replace the body of `join_group` (keep the decorator and signature) with:

```python
@router.post("/join/{invite_token}", response_model=GroupDetail)
def join_group(
    invite_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = (
        db.query(Group)
        .filter(Group.invite_token == invite_token, Group.deleted_at.is_(None))
        .first()
    )
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link"
        )
    _add_member(db, group, current_user.id)
    db.commit()
    return _group_detail(db, group)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_group_join.py -v`
Expected: both PASS.

- [ ] **Step 5: Run the existing group/settle suite for regressions**

Run: `cd backend && python -m pytest tests/test_settle_archive.py -v`
Expected: all PASS (the re-split-on-join behavior is unchanged for unsettled groups).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/groups.py backend/tests/test_group_join.py
git commit -m "refactor: extract _add_member; block joining settled groups"
```

---

### Task 2: Short join code

**Files:**
- Modify: `backend/app/routers/groups.py`
- Test: `backend/tests/test_group_join.py`

**Interfaces:**
- Produces `_generate_code() -> str` and `_unique_invite_code(db) -> str` in `groups.py`; `create_group` uses `_unique_invite_code(db)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_group_join.py`:

```python
class ShortCodeTest(GroupJoinTest):
    def test_create_group_gets_short_code(self):
        res = self.client.post(
            "/api/groups/",
            json={"name": "Beach"},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 201)
        # The created group's code is short and from the unambiguous alphabet.
        with self.Session() as s:
            g = s.query(Group).filter(Group.name == "Beach").one()
        self.assertEqual(len(g.invite_token), 6)
        self.assertTrue(all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in g.invite_token))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_group_join.py::ShortCodeTest -v`
Expected: FAIL — token is the 16-char `token_urlsafe`, not a 6-char code.

- [ ] **Step 3: Add the code helpers and use them in `create_group`**

In `backend/app/routers/groups.py`, add near the top (after the router definition):

```python
import secrets

INVITE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 6


def _generate_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


def _unique_invite_code(db: Session) -> str:
    for _ in range(10):
        code = _generate_code()
        if not db.query(Group).filter(Group.invite_token == code).first():
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate an invite code",
    )
```

In `create_group`, set the token explicitly:

```python
    group = Group(
        name=body.name.strip(),
        description=body.description,
        created_by=current_user.id,
        invite_token=_unique_invite_code(db),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_group_join.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/groups.py backend/tests/test_group_join.py
git commit -m "feat: short unambiguous group invite codes"
```

---

### Task 3: QR code on the group page

**Files:**
- Modify: `frontend/package.json` (add `qrcode.react`)
- Modify: `frontend/src/pages/GroupDetailPage.jsx`

**Interfaces:** Consumes the existing `inviteLink` state and `/groups/{id}/invite` endpoint.

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install qrcode.react`
Expected: `qrcode.react` added to `package.json` dependencies; lockfile updated.

- [ ] **Step 2: Render the code + QR in the invite modal**

In `frontend/src/pages/GroupDetailPage.jsx`, add the import at the top:

```jsx
import { QRCodeSVG } from 'qrcode.react';
```

The invite modal currently shows a readonly link input. Replace the modal's inner content (the block starting at `<h2 ...>Invite Link</h2>` through the readonly `<input ... value={inviteLink} ... />`) with code + QR + link. The full modal becomes:

```jsx
      {inviteLink && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="glass-strong w-full max-w-sm space-y-4 p-6">
            <h2 className="text-[17px] font-semibold text-white">Invite to group</h2>
            <div className="flex flex-col items-center gap-3">
              <div className="rounded-2xl bg-white p-3">
                <QRCodeSVG value={inviteLink} size={160} />
              </div>
              <p className="text-[13px] text-white/55">Scan to join, or share the code</p>
              <div className="text-2xl font-bold tracking-[0.3em] text-white">
                {group.invite_token}
              </div>
            </div>
            <input
              readOnly
              value={inviteLink}
              className="w-full rounded-xl bg-white/10 px-3 py-2 text-[13px] text-white/80 outline-none"
              onFocus={(e) => e.target.select()}
            />
            <div className="flex gap-3">
              <button
                onClick={handleCopy}
                className="flex-1 rounded-xl bg-violet-500 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80"
              >
                {copied ? 'Copied!' : 'Copy link'}
              </button>
              <button
                onClick={() => { setInviteLink(''); setCopied(false); }}
                className="flex-1 rounded-xl bg-white/10 py-2 text-[14px] font-medium text-white/70 transition-opacity hover:opacity-80"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
```

Note: `group.invite_token` is the short code; `GroupDetail`/`GroupOut` already include it? It does NOT — `GroupOut` has no `invite_token`. Fetch it from the existing `/groups/{id}/invite` call: `handleInvite` already sets `inviteLink` from `data.invite_token`; also store the raw code. Update `handleInvite`:

```jsx
  const [inviteCode, setInviteCode] = useState('');
  const handleInvite = async () => {
    try {
      const { data } = await api.get(`/groups/${id}/invite`);
      setInviteCode(data.invite_token);
      setInviteLink(`${window.location.origin}/invite/${data.invite_token}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get invite link');
    }
  };
```

and in the modal use `{inviteCode}` instead of `{group.invite_token}`.

- [ ] **Step 3: Verify the build**

Run: `cd frontend && npm run build`
Expected: builds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/pages/GroupDetailPage.jsx
git commit -m "feat: show join code and QR in the group invite modal"
```

---

# Phase B — Invite friends directly

### Task 4: Add-member-by-friend endpoint

**Files:**
- Modify: `backend/app/routers/groups.py`, `backend/app/schemas/group.py`
- Test: `backend/tests/test_group_join.py`

**Interfaces:**
- Consumes `_add_member` (Task 1), `friends_svc.are_friends`.
- Produces `POST /api/groups/{group_id}/members` `{user_id}` → `GroupDetail`; `AddMemberRequest{user_id: str}`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_group_join.py` (add at top: `from app.models.friendship import Friendship, FriendshipStatus`):

```python
class AddFriendMemberTest(GroupJoinTest):
    def _befriend(self, a, b):
        self.db.add(
            Friendship(
                requester_id=a.id, addressee_id=b.id, status=FriendshipStatus.ACCEPTED
            )
        )
        self.db.commit()

    def test_add_friend_to_group(self):
        self._befriend(self.owner, self.joiner)
        res = self.client.post(
            f"/api/groups/{self.group.id}/members",
            json={"user_id": self.joiner.id},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_add_non_friend_rejected(self):
        res = self.client.post(
            f"/api/groups/{self.group.id}/members",
            json={"user_id": self.joiner.id},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_group_join.py::AddFriendMemberTest -v`
Expected: FAIL — endpoint 404/405 (not defined).

- [ ] **Step 3: Add the schema**

In `backend/app/schemas/group.py`, add:

```python
class AddMemberRequest(BaseModel):
    user_id: str
```

- [ ] **Step 4: Add the endpoint**

In `backend/app/routers/groups.py`, add the import near the other imports:

```python
from app.services import friends as friends_svc
from app.schemas.group import AddMemberRequest
```

(merge `AddMemberRequest` into the existing `from app.schemas.group import (...)` block instead if present). Add the endpoint (place it after `get_invite`):

```python
@router.post("/{group_id}/members", response_model=GroupDetail)
def add_member(
    group_id: str,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    if not friends_svc.are_friends(db, current_user.id, body.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add your friends",
        )
    _add_member(db, group, body.user_id)
    db.commit()
    return _group_detail(db, group)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_group_join.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/groups.py backend/app/schemas/group.py backend/tests/test_group_join.py
git commit -m "feat: add accepted friends to a group directly"
```

---

### Task 5: Add-friends UI in the group page

**Files:**
- Modify: `frontend/src/pages/GroupDetailPage.jsx`

**Interfaces:** Consumes `GET /api/friends` and `POST /api/groups/{id}/members`.

- [ ] **Step 1: Load friends and render an add-friends section**

In `frontend/src/pages/GroupDetailPage.jsx`:

Add state and a loader. Inside the component, add:

```jsx
  const [friends, setFriends] = useState([]);

  useEffect(() => {
    api
      .get('/friends')
      .then(({ data }) => setFriends(data))
      .catch(() => {});
  }, []);

  const addFriend = async (friendId) => {
    setError('');
    try {
      const { data } = await api.post(`/groups/${id}/members`, { user_id: friendId });
      setGroup(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add friend');
    }
  };
```

Render an "Add friends" card (only when the group is not settled). Insert it right after the member-row `</div>` that closes the header `glass` card (after the block containing the member avatars + invite `+` button), before `<ErrorMessage message={error} />`:

```jsx
      {!isSettled && (() => {
        const memberIds = new Set(group.members.map((m) => m.id));
        const addable = friends.filter((f) => !memberIds.has(f.id));
        if (addable.length === 0) return null;
        return (
          <div className="glass space-y-2 p-4">
            <p className="text-[13px] font-medium text-white/55">Add friends</p>
            {addable.map((f) => (
              <div key={f.id} className="flex items-center justify-between">
                <span className="text-[15px] text-white/85">
                  {f.username || f.phone_number}
                </span>
                <Button variant="secondary" onClick={() => addFriend(f.id)}>
                  Add
                </Button>
              </div>
            ))}
          </div>
        );
      })()}
```

- [ ] **Step 2: Verify the build**

Run: `cd frontend && npm run build`
Expected: builds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/GroupDetailPage.jsx
git commit -m "feat: add friends to a group from the group page"
```

---

# Phase C — Invite by phone

### Task 6: GroupInvitation model + migration

**Files:**
- Create: `backend/app/models/group_invitation.py`, `backend/alembic/versions/0005_group_invitations.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_group_invitations.py` (new)

**Interfaces:**
- Produces `GroupInvitationStatus` (`PENDING`, `ACCEPTED`) and `GroupInvitation` with columns `id, group_id, invited_user_id, invited_by, status, created_at, responded_at`, unique `(group_id, invited_user_id)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_group_invitations.py`:

```python
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-group-invitations")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.group import Group
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
from app.models.user import User


class GroupInvitationModelTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.flush()
        g = Group(name="Trip", created_by=a.id, invite_token="ABCDEF")
        self.db.add(g)
        self.db.flush()
        return a, b, g

    def test_defaults(self):
        a, b, g = self._seed()
        inv = GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id)
        self.db.add(inv)
        self.db.commit()
        row = self.db.query(GroupInvitation).one()
        self.assertEqual(row.status, GroupInvitationStatus.PENDING)
        self.assertIsNotNone(row.created_at)
        self.assertIsNone(row.responded_at)

    def test_unique_pair(self):
        a, b, g = self._seed()
        self.db.add(GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id))
        self.db.commit()
        self.db.add(GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_group_invitations.py -v`
Expected: FAIL — `ModuleNotFoundError: app.models.group_invitation`.

- [ ] **Step 3: Create the model**

Create `backend/app/models/group_invitation.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import generate_uuid, utcnow


class GroupInvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    __table_args__ = (
        UniqueConstraint("group_id", "invited_user_id", name="uq_group_invitation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    invited_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    invited_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[GroupInvitationStatus] = mapped_column(
        Enum(GroupInvitationStatus, name="groupinvitationstatus"),
        default=GroupInvitationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Export the model**

In `backend/app/models/__init__.py`, add the import and `__all__` entries:

```python
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
```

and add `"GroupInvitation"`, `"GroupInvitationStatus"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_group_invitations.py -v`
Expected: both PASS.

- [ ] **Step 6: Create the migration**

Create `backend/alembic/versions/0005_group_invitations.py`:

```python
"""group invitations table

Revision ID: 0005
Revises: 0004
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("invited_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", name="groupinvitationstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("group_id", "invited_user_id", name="uq_group_invitation"),
    )


def downgrade() -> None:
    op.drop_table("group_invitations")
```

- [ ] **Step 7: Verify the migration**

Run: `cd backend && alembic upgrade head && alembic current`
Expected: current shows `0005 (head)`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/group_invitation.py backend/app/models/__init__.py backend/alembic/versions/0005_group_invitations.py backend/tests/test_group_invitations.py
git commit -m "feat: add group invitation model and migration"
```

---

### Task 7: Group-invitation endpoints

**Files:**
- Create: `backend/app/routers/group_invitations.py`
- Modify: `backend/app/main.py`, `backend/app/schemas/group.py`
- Test: `backend/tests/test_group_invitations.py`

**Interfaces:**
- Consumes `_add_member`, `get_group_or_404`, `require_membership` from `groups`.
- Produces router `group_invitations.router` (prefix `/api/group-invitations`):
  - `POST /api/group-invitations` `{group_id, phone_number}` → 201.
  - `GET /api/group-invitations` → `list[GroupInvitationOut]` (my pending).
  - `POST /api/group-invitations/{id}/accept` → `GroupDetail`.
  - `POST /api/group-invitations/{id}/decline` → 204.
- Schemas `GroupInviteCreate`, `GroupInvitationOut`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_group_invitations.py`. Add imports at top:

```python
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.models.group import Membership
```

Add the class:

```python
class GroupInvitationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()
        self.owner = User(phone_number="+15550000001", username="Owner")
        self.invitee = User(phone_number="+15550000002", username="Invitee")
        self.db.add_all([self.owner, self.invitee])
        self.db.flush()
        self.group = Group(name="Trip", created_by=self.owner.id, invite_token="ABCDEF")
        self.db.add(self.group)
        self.db.flush()
        self.db.add(Membership(user_id=self.owner.id, group_id=self.group.id))
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

    def test_invite_by_phone_and_accept(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 201)

        pending = self.client.get(
            "/api/group-invitations", headers=self._auth(self.invitee)
        ).json()
        self.assertEqual(len(pending), 1)
        inv_id = pending[0]["id"]

        res = self.client.post(
            f"/api/group-invitations/{inv_id}/accept",
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_invite_unknown_phone_404(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": "+15559999999"},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 404)

    def test_non_member_cannot_invite(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 403)

    def test_decline_deletes(self):
        self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.owner),
        )
        inv_id = self.db.query(GroupInvitation).one().id
        res = self.client.post(
            f"/api/group-invitations/{inv_id}/decline",
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 204)
        with self.Session() as s:
            self.assertEqual(s.query(GroupInvitation).count(), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_group_invitations.py::GroupInvitationApiTest -v`
Expected: FAIL — 404 on `/api/group-invitations` (router not registered).

- [ ] **Step 3: Add the schemas**

In `backend/app/schemas/group.py`, add:

```python
class GroupInviteCreate(BaseModel):
    group_id: str
    phone_number: str = Field(min_length=3, max_length=20)


class GroupInvitationOut(BaseModel):
    id: str
    group_id: str
    group_name: str
    invited_by_username: str | None
    created_at: datetime
```

- [ ] **Step 4: Create the router**

Create `backend/app/routers/group_invitations.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.group import Group, Membership
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
from app.models.user import User, utcnow
from app.routers.groups import (
    _add_member,
    _group_detail,
    get_group_or_404,
    require_membership,
)
from app.schemas.group import GroupDetail, GroupInviteCreate, GroupInvitationOut

router = APIRouter(prefix="/api/group-invitations", tags=["group-invitations"])


@router.post("", response_model=GroupInvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: GroupInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, body.group_id)
    require_membership(db, body.group_id, current_user.id)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    target = db.query(User).filter(User.phone_number == body.phone_number).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that phone number"
        )
    already_member = (
        db.query(Membership)
        .filter(Membership.group_id == group.id, Membership.user_id == target.id)
        .first()
    )
    if already_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already a member"
        )
    existing = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.group_id == group.id,
            GroupInvitation.invited_user_id == target.id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already invited"
        )
    inv = GroupInvitation(
        group_id=group.id, invited_user_id=target.id, invited_by=current_user.id
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return GroupInvitationOut(
        id=inv.id,
        group_id=group.id,
        group_name=group.name,
        invited_by_username=current_user.username,
        created_at=inv.created_at,
    )


@router.get("", response_model=list[GroupInvitationOut])
def my_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.invited_user_id == current_user.id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .order_by(GroupInvitation.created_at.desc())
        .all()
    )
    if not rows:
        return []
    groups = {
        g.id: g
        for g in db.query(Group).filter(
            Group.id.in_([r.group_id for r in rows])
        ).all()
    }
    inviters = {
        u.id: u.username
        for u in db.query(User).filter(
            User.id.in_([r.invited_by for r in rows])
        ).all()
    }
    return [
        GroupInvitationOut(
            id=r.id,
            group_id=r.group_id,
            group_name=groups[r.group_id].name if r.group_id in groups else "",
            invited_by_username=inviters.get(r.invited_by),
            created_at=r.created_at,
        )
        for r in rows
        if r.group_id in groups and groups[r.group_id].deleted_at is None
    ]


def _get_pending_or_404(db: Session, invitation_id: str, user_id: str) -> GroupInvitation:
    inv = (
        db.query(GroupInvitation)
        .filter(
            GroupInvitation.id == invitation_id,
            GroupInvitation.invited_user_id == user_id,
            GroupInvitation.status == GroupInvitationStatus.PENDING,
        )
        .first()
    )
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    return inv


@router.post("/{invitation_id}/accept", response_model=GroupDetail)
def accept_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _get_pending_or_404(db, invitation_id, current_user.id)
    group = get_group_or_404(db, inv.group_id)
    _add_member(db, group, current_user.id)
    inv.status = GroupInvitationStatus.ACCEPTED
    inv.responded_at = utcnow()
    db.commit()
    return _group_detail(db, group)


@router.post("/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = _get_pending_or_404(db, invitation_id, current_user.id)
    db.delete(inv)
    db.commit()
```

IMPORTANT: the schema import line above contains an intentional typo placeholder — write it correctly as:

```python
from app.schemas.group import GroupDetail, GroupInviteCreate, GroupInvitationOut
```

(remove the duplicate/garbled import line; a single correct import of `GroupDetail, GroupInviteCreate, GroupInvitationOut` plus `from app.routers.groups import _group_detail`).

Note: `_group_detail` and `_add_member` are module-level functions in `groups.py` (underscore-prefixed but importable). The `GroupInviteCreate`/`GroupInvitationOut` schemas come from Task 7 Step 3.

- [ ] **Step 5: Register the router**

In `backend/app/main.py`: add `group_invitations` to the routers import and `app.include_router(group_invitations.router)` after the others.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_group_invitations.py -v`
Expected: all PASS.

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: only the 4 known pre-existing OTP failures in `test_public_readiness.py`; everything else passes.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/group_invitations.py backend/app/main.py backend/app/schemas/group.py backend/tests/test_group_invitations.py
git commit -m "feat: group invitation endpoints (invite by phone, accept, decline)"
```

---

### Task 8: Phone-invite UI + pending invites + badge

**Files:**
- Modify: `frontend/src/pages/GroupDetailPage.jsx`, `frontend/src/pages/HomePage.jsx`, `frontend/src/components/Navbar.jsx`

**Interfaces:** Consumes `POST /api/group-invitations`, `GET /api/group-invitations`, `POST /api/group-invitations/{id}/accept|decline`.

- [ ] **Step 1: Invite-by-phone input in the group invite modal**

In `frontend/src/pages/GroupDetailPage.jsx`, add a `formatPhone` helper at module scope (copy verbatim from `FriendsPage.jsx`):

```jsx
function formatPhone(value) {
  let d = value.replace(/\D/g, '');
  if (d.length === 11 && d.startsWith('1')) d = d.slice(1);
  d = d.slice(0, 10);
  const parts = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 10)].filter(Boolean);
  return parts.join('-');
}
```

Add state and handler in the component:

```jsx
  const [invitePhone, setInvitePhone] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');

  const sendPhoneInvite = async () => {
    setError('');
    setInviteNotice('');
    let digits = invitePhone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('1')) digits = digits.slice(1);
    if (digits.length !== 10) {
      setError('Enter a valid 10-digit US phone number');
      return;
    }
    try {
      await api.post('/group-invitations', {
        group_id: id,
        phone_number: `+1${digits}`,
      });
      setInvitePhone('');
      setInviteNotice('Invite sent');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send invite');
    }
  };
```

In the invite modal (Task 3), add an invite-by-phone block above the Copy/Close buttons:

```jsx
            <div className="space-y-2 border-t border-white/10 pt-3">
              <p className="text-[13px] font-medium text-white/55">Invite by phone</p>
              <div className="flex gap-2">
                <input
                  type="tel"
                  inputMode="numeric"
                  placeholder="909-555-0101"
                  value={invitePhone}
                  onChange={(e) => setInvitePhone(formatPhone(e.target.value))}
                  className="min-w-0 flex-1 rounded-xl bg-white/10 px-3 py-2 text-[13px] text-white placeholder-white/30 outline-none"
                />
                <button
                  onClick={sendPhoneInvite}
                  disabled={!invitePhone.trim()}
                  className="shrink-0 rounded-xl bg-violet-500 px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
                >
                  Invite
                </button>
              </div>
              {inviteNotice && <p className="text-[12px] text-emerald-400">{inviteNotice}</p>}
            </div>
```

- [ ] **Step 2: Pending group invites on HomePage**

In `frontend/src/pages/HomePage.jsx`, add state + load + accept/decline, and render a section above "My Groups":

```jsx
  const [invites, setInvites] = useState([]);

  const loadInvites = () =>
    api
      .get('/group-invitations')
      .then(({ data }) => setInvites(data))
      .catch(() => {});

  useEffect(() => {
    loadInvites();
  }, []);

  const respondInvite = async (inviteId, action) => {
    try {
      await api.post(`/group-invitations/${inviteId}/${action}`);
      await loadInvites();
      if (action === 'accept') {
        const { data } = await api.get('/groups/');
        setGroups(data);
      }
    } catch {
      // ignore; list reload covers state
    }
  };
```

Render (place right after the `<h1>My Groups</h1>` + `<ErrorMessage>` block, before the loading/groups block):

```jsx
      {invites.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-white/90">Group invitations</h2>
          {invites.map((inv) => (
            <div key={inv.id} className="glass flex items-center justify-between p-4">
              <div>
                <p className="text-[15px] font-medium text-white/85">{inv.group_name}</p>
                <p className="text-[13px] text-white/45">
                  from {inv.invited_by_username || 'someone'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => respondInvite(inv.id, 'accept')}
                  className="rounded-xl bg-violet-500 px-3 py-1.5 text-[13px] font-medium text-white hover:opacity-80"
                >
                  Join
                </button>
                <button
                  onClick={() => respondInvite(inv.id, 'decline')}
                  className="rounded-xl bg-white/10 px-3 py-1.5 text-[13px] font-medium text-white/70 hover:opacity-80"
                >
                  Decline
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
```

- [ ] **Step 3: Group-invite badge on the Navbar home link**

In `frontend/src/components/Navbar.jsx`, add a second count state and poll, and badge the Settlo home link:

```jsx
  const [inviteCount, setInviteCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const fetchInvites = () =>
      api
        .get('/group-invitations')
        .then(({ data }) => active && setInviteCount(data.length))
        .catch(() => {});
    fetchInvites();
    const id = setInterval(fetchInvites, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [user]);
```

Wrap the Settlo home `Link` so the badge can be absolutely positioned. Replace the existing home `Link`:

```jsx
        <Link
          to="/"
          className="relative text-lg font-semibold tracking-wide text-white"
        >
          Settlo
          {inviteCount > 0 && (
            <span className="absolute -right-3 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white shadow-[0_0_8px_rgba(239,68,68,0.5)]">
              {inviteCount > 99 ? '99+' : inviteCount}
            </span>
          )}
        </Link>
```

- [ ] **Step 4: Verify the build**

Run: `cd frontend && npm run build`
Expected: builds with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GroupDetailPage.jsx frontend/src/pages/HomePage.jsx frontend/src/components/Navbar.jsx
git commit -m "feat: invite by phone UI, pending invites on home, invite badge"
```

---

## Final verification

- [ ] `cd backend && python -m pytest -q` — only the 4 pre-existing OTP failures remain.
- [ ] `cd backend && alembic upgrade head` → `0005 (head)`.
- [ ] `cd frontend && npm run build` — clean.
- [ ] Manual: create group (short code shown), open invite modal (QR + code + phone invite), add a friend directly, invite a second account by phone → it sees the invite on Home with a badge → Join adds them.

## Notes for the implementer

- `_add_member` is the single source of truth for joining; do not duplicate membership/re-split logic in the new endpoints.
- The phone path stores/compares `+1XXXXXXXXXX`; the frontend normalizes before sending.
- `qrcode.react` exports `QRCodeSVG` (named import).
