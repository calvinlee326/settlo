# Settle & Archive to Payment History — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A group is used once: add expenses → Settle Up shows who owes whom → one Confirm archives the whole group (expenses + settlement) into an expandable Payment History on the home page. Settled groups are read-only; deleting from history is a soft delete.

**Architecture:** Add `settled_at` / `settled_by` / `deleted_at` to `groups`. A confirm endpoint computes the settlement plan, persists it as paid `Settlement` rows, and stamps `settled_at`. All group lists filter `deleted_at IS NULL`; the home page splits active (`settled_at` null) from history (`settled_at` set).

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (SQLite dev / Postgres prod); React 18 + Vite + Tailwind + Axios. Backend tests use `unittest` calling router functions directly.

**Spec:** `docs/superpowers/specs/2026-06-15-settle-archive-history-design.md`

## Running tests
Always prefix with `DEV_OTP_CODE=` (a local-only OTP bypass otherwise fails 4 unrelated tests):
```bash
cd backend && source .venv/bin/activate && DEV_OTP_CODE= python -m unittest discover -s tests -v
```
Never `git add` `backend/app/core/config.py` or `backend/app/services/otp.py` (uncommitted local bypass). Commit by explicit path; never `git add -A`.

## File structure
- `backend/app/models/group.py` — add `settled_at`, `settled_by`, `deleted_at` columns.
- `backend/app/schemas/group.py` — add `settled_at`, `total` to `GroupOut`.
- `backend/alembic/versions/0002_group_settle_archive.py` — new migration.
- `backend/app/routers/groups.py` — soft delete, `deleted_at` filtering, `settled_at`/`total` in list & detail.
- `backend/app/routers/settlements.py` — new `POST /confirm` endpoint.
- `backend/app/routers/expenses.py` — block create/delete when settled.
- `backend/tests/test_settle_archive.py` — new test module.
- `frontend/src/components/SettlementItem.jsx` — render no button when `onPay` is null.
- `frontend/src/components/PaymentHistoryItem.jsx` — new expandable history card.
- `frontend/src/pages/SettlementPage.jsx` — single "Confirm & settle".
- `frontend/src/pages/HomePage.jsx` — split active vs Payment History.
- `frontend/src/pages/GroupDetailPage.jsx` — read-only when settled.

---

## Task 1: Group model + schema fields

**Files:** Modify `backend/app/models/group.py`, `backend/app/schemas/group.py`. Test `backend/tests/test_settle_archive.py`.

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_settle_archive.py`:

```python
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-settle-archive")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.group import Group, Membership
from app.models.user import User


class SettleArchiveTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _group(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.flush()
        g = Group(name="Trip", created_by=a.id)
        self.db.add(g)
        self.db.flush()
        self.db.add_all([
            Membership(user_id=a.id, group_id=g.id),
            Membership(user_id=b.id, group_id=g.id),
        ])
        self.db.commit()
        return a, b, g

    def _expense(self, group, payer, a, b, total, share_a, share_b):
        e = Expense(
            group_id=group.id, paid_by=payer.id, title="X",
            amount=Decimal(total), created_by=payer.id,
        )
        self.db.add(e)
        self.db.flush()
        self.db.add_all([
            ExpenseSplit(expense_id=e.id, user_id=a.id, amount=Decimal(share_a)),
            ExpenseSplit(expense_id=e.id, user_id=b.id, amount=Decimal(share_b)),
        ])
        self.db.commit()
        return e

    def test_group_settle_archive_columns_default_none(self):
        a, b, g = self._group()
        reloaded = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNone(reloaded.settled_at)
        self.assertIsNone(reloaded.settled_by)
        self.assertIsNone(reloaded.deleted_at)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → FAIL: `AttributeError: ... 'settled_at'` (column doesn't exist).

- [ ] **Step 3: Add the columns**

In `backend/app/models/group.py`, in the `Group` class, after the `created_at` column and before the `memberships` relationship, add:
```python
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settled_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```
(`DateTime`, `String`, `ForeignKey`, `Mapped`, `mapped_column` are already imported in this file.)

In `backend/app/schemas/group.py`, add two fields to `GroupOut` (after `created_at`):
```python
    settled_at: datetime | None = None
    total: float = 0
```

- [ ] **Step 4: Run to verify it passes** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → PASS.

- [ ] **Step 5: Full suite** — `cd backend && DEV_OTP_CODE= python -m unittest discover -s tests` → OK.

- [ ] **Step 6: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add backend/app/models/group.py backend/app/schemas/group.py backend/tests/test_settle_archive.py
git commit -m "feat: add settled_at/settled_by/deleted_at to groups"
```

---

## Task 2: Migration 0002

**Files:** Create `backend/alembic/versions/0002_group_settle_archive.py`.

- [ ] **Step 1: Write the migration**
```python
"""group settle + soft delete

Revision ID: 0002
Revises: 0001
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("settled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("settled_by", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("settled_by")
        batch_op.drop_column("settled_at")
```

- [ ] **Step 2: Verify on a throwaway DB**
```bash
cd backend && source .venv/bin/activate
DATABASE_URL="sqlite:///./_migtest.db" DEV_OTP_CODE= alembic upgrade head
DATABASE_URL="sqlite:///./_migtest.db" python -c "import sqlite3;c=sqlite3.connect('_migtest.db');print([r[1] for r in c.execute('PRAGMA table_info(groups)')])"
DATABASE_URL="sqlite:///./_migtest.db" DEV_OTP_CODE= alembic downgrade -1
DATABASE_URL="sqlite:///./_migtest.db" python -c "import sqlite3;c=sqlite3.connect('_migtest.db');print('settled_at' in [r[1] for r in c.execute('PRAGMA table_info(groups)')])"
rm -f _migtest.db
```
Expected: groups columns include `settled_at`, `settled_by`, `deleted_at`; after downgrade prints `False`.

- [ ] **Step 3: Apply to dev DB** — `cd backend && DEV_OTP_CODE= alembic upgrade head` → "Running upgrade 0001 -> 0002".

- [ ] **Step 4: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add backend/alembic/versions/0002_group_settle_archive.py
git commit -m "feat: migration for group settle/soft-delete columns"
```

---

## Task 3: groups.py — soft delete, filtering, settled_at + total

**Files:** Modify `backend/app/routers/groups.py`. Test in `backend/tests/test_settle_archive.py`.

- [ ] **Step 1: Write failing tests** — add to `SettleArchiveTest`:
```python
    def test_get_group_or_404_excludes_soft_deleted(self):
        from fastapi import HTTPException
        from app.routers.groups import get_group_or_404
        from app.models.user import utcnow

        a, b, g = self._group()
        g.deleted_at = utcnow()
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            get_group_or_404(self.db, g.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_group_is_soft(self):
        from app.routers.groups import delete_group, list_my_groups

        a, b, g = self._group()
        delete_group(g.id, current_user=a, db=self.db)
        # Row still exists, deleted_at set
        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.deleted_at)
        # No longer listed for the creator
        listed = list_my_groups(current_user=a, db=self.db)
        self.assertEqual(listed, [])

    def test_list_my_groups_reports_total_and_settled_at(self):
        from app.routers.groups import list_my_groups

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        listed = list_my_groups(current_user=a, db=self.db)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].total, 10.0)
        self.assertIsNone(listed[0].settled_at)
```

- [ ] **Step 2: Run to verify they fail** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → FAILs (soft delete not implemented; total missing).

- [ ] **Step 3: Implement**

In `backend/app/routers/groups.py`:

(a) Add imports: change `from sqlalchemy import or_` to `from sqlalchemy import func, or_`, and change `from app.models.user import User` to `from app.models.user import User, utcnow`.

(b) `get_group_or_404` — exclude soft-deleted:
```python
def get_group_or_404(db: Session, group_id: str) -> Group:
    group = (
        db.query(Group)
        .filter(Group.id == group_id, Group.deleted_at.is_(None))
        .first()
    )
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group
```

(c) `list_my_groups` — filter deleted, add total + settled_at:
```python
@router.get("/", response_model=list[GroupOut])
def list_my_groups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    groups = (
        db.query(Group)
        .join(Membership, Membership.group_id == Group.id)
        .filter(Membership.user_id == current_user.id, Group.deleted_at.is_(None))
        .order_by(Group.created_at.desc())
        .all()
    )
    counts = {
        g.id: db.query(Membership).filter(Membership.group_id == g.id).count()
        for g in groups
    }
    totals: dict[str, float] = {}
    group_ids = [g.id for g in groups]
    if group_ids:
        rows = (
            db.query(Expense.group_id, func.sum(Expense.amount))
            .filter(Expense.group_id.in_(group_ids))
            .group_by(Expense.group_id)
            .all()
        )
        totals = {gid: float(total or 0) for gid, total in rows}
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            max_members=g.max_members,
            created_by=g.created_by,
            created_at=g.created_at,
            member_count=counts[g.id],
            settled_at=g.settled_at,
            total=totals.get(g.id, 0.0),
        )
        for g in groups
    ]
```

(d) `_group_detail` — include `settled_at`. Find the `GroupDetail(` (or `_group_detail` return) construction and add `settled_at=group.settled_at,` to the keyword arguments. Read the function first; it builds a `GroupDetail(...)`. Add the field.

(e) `delete_group` — replace the whole body after the 403 check with a soft delete:
```python
@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    if group.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group creator can delete the group",
        )
    group.deleted_at = utcnow()
    db.commit()
```
(The previous hard-delete of expense_splits/expenses/settlements/memberships is removed. `ExpenseSplit`/`Settlement`/`Expense` may still be imported for other handlers — leave the imports as-is; do not remove imports you are unsure about.)

- [ ] **Step 4: Run to verify pass** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → PASS.

- [ ] **Step 5: Full suite** — `cd backend && DEV_OTP_CODE= python -m unittest discover -s tests` → OK. If a pre-existing test relied on `delete_group` hard-deleting, report it as DONE_WITH_CONCERNS with the test name (do not change that behavior without escalating).

- [ ] **Step 6: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add backend/app/routers/groups.py backend/tests/test_settle_archive.py
git commit -m "feat: soft-delete groups; expose total and settled_at"
```

---

## Task 4: Confirm-settle endpoint

**Files:** Modify `backend/app/routers/settlements.py`. Test in `backend/tests/test_settle_archive.py`.

- [ ] **Step 1: Write failing tests** — add to `SettleArchiveTest`:
```python
    def test_confirm_archives_group_and_persists_settlement(self):
        from app.routers.settlements import confirm_settlement, get_settlements

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")  # B owes A 5
        confirm_settlement(g.id, current_user=a, db=self.db)

        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(row.settled_by, a.id)

        persisted = self.db.query(Settlement).filter(
            Settlement.group_id == g.id, Settlement.is_paid.is_(True)
        ).all()
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].from_user, b.id)
        self.assertEqual(persisted[0].to_user, a.id)

        result = get_settlements(g.id, current_user=a, db=self.db)
        self.assertEqual(result.settlements, [])
        self.assertEqual(len(result.paid_settlements), 1)
        self.assertTrue(all(abs(bal.balance) < 0.005 for bal in result.balances))

    def test_confirm_rejects_when_already_settled(self):
        from fastapi import HTTPException
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            confirm_settlement(g.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_confirm_rejects_when_no_expenses(self):
        from fastapi import HTTPException
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        with self.assertRaises(HTTPException) as ctx:
            confirm_settlement(g.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_confirm_with_zero_debt_still_archives(self):
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "10.00", "0.00")  # A paid, A owes all -> net 0
        confirm_settlement(g.id, current_user=a, db=self.db)
        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(
            self.db.query(Settlement).filter(Settlement.group_id == g.id).count(), 0
        )
```

- [ ] **Step 2: Run to verify they fail** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → FAIL: `cannot import name 'confirm_settlement'`.

- [ ] **Step 3: Implement**

In `backend/app/routers/settlements.py`:
(a) Change `from app.models.group import Membership` to `from app.models.group import Group, Membership`.
(b) Add the endpoint (place it after `get_settlements`, before `mark_paid`):
```python
@router.post("/confirm", response_model=SettlementResult)
def confirm_settlement(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)

    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    has_expense = (
        db.query(Expense.id).filter(Expense.group_id == group_id).first()
    )
    if has_expense is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add an expense before settling",
        )

    balances = _compute_balances(db, group_id)
    transactions = calculate_settlements(balances)
    now = _utcnow()
    for t in transactions:
        db.add(
            Settlement(
                group_id=group_id,
                from_user=t["from_user"],
                to_user=t["to_user"],
                amount=t["amount"],
                is_paid=True,
                paid_at=now,
            )
        )
    group.settled_at = now
    group.settled_by = current_user.id
    db.commit()

    return get_settlements(group_id, current_user=current_user, db=db)
```

- [ ] **Step 4: Run to verify pass** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → PASS.

- [ ] **Step 5: Full suite** — `cd backend && DEV_OTP_CODE= python -m unittest discover -s tests` → OK.

- [ ] **Step 6: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add backend/app/routers/settlements.py backend/tests/test_settle_archive.py
git commit -m "feat: confirm-settle endpoint archives group and records settlement"
```

---

## Task 5: Block expense mutations on settled groups

**Files:** Modify `backend/app/routers/expenses.py`. Test in `backend/tests/test_settle_archive.py`.

- [ ] **Step 1: Write failing tests** — add to `SettleArchiveTest`:
```python
    def test_create_expense_blocked_when_settled(self):
        from fastapi import HTTPException
        from app.routers.expenses import create_expense
        from app.routers.settlements import confirm_settlement
        from app.schemas.expense import ExpenseCreate

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)

        body = ExpenseCreate(
            title="Late", amount=Decimal("4.00"), paid_by=a.id, split_type="EQUAL"
        )
        with self.assertRaises(HTTPException) as ctx:
            create_expense(g.id, body, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_delete_expense_blocked_when_settled(self):
        from fastapi import HTTPException
        from app.routers.expenses import delete_expense
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        e = self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            delete_expense(g.id, e.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)
```
(Read `backend/app/schemas/expense.py` to confirm `ExpenseCreate`'s fields/types match this construction; adjust the kwargs if the schema differs — e.g. `split_type` enum value.)

- [ ] **Step 2: Run to verify they fail** — they should NOT raise 400 yet (creation/deletion succeeds on a settled group).

- [ ] **Step 3: Implement**

In `backend/app/routers/expenses.py`:
- In `create_expense`, the function calls `get_group_or_404(db, group_id)` — capture it and guard. Change that line and add the check immediately after:
```python
    group = get_group_or_404(db, group_id)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    require_membership(db, group_id, current_user.id)
```
- In `delete_expense`, it already does `group = get_group_or_404(db, group_id)`. Right after the `require_membership(...)` line, add:
```python
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
```

- [ ] **Step 4: Run to verify pass** — `cd backend && DEV_OTP_CODE= python -m unittest tests.test_settle_archive -v` → PASS.

- [ ] **Step 5: Full suite** — `cd backend && DEV_OTP_CODE= python -m unittest discover -s tests` → OK.

- [ ] **Step 6: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add backend/app/routers/expenses.py backend/tests/test_settle_archive.py
git commit -m "feat: block expense changes on a settled group"
```

---

## Task 6: SettlementItem (no button when read-only) + SettlementPage Confirm

**Files:** Modify `frontend/src/components/SettlementItem.jsx`, `frontend/src/pages/SettlementPage.jsx`. Verify with `npm run build`.

- [ ] **Step 1: SettlementItem — render no action when `onPay` is null**

In `frontend/src/components/SettlementItem.jsx`, find the trailing conditional that renders the Paid badge or the "Mark as Paid" button:
```jsx
      {settlement.is_paid ? (
        <span ...>...Paid</span>
      ) : (
        <Button onClick={onPay} disabled={paying} className="shrink-0 px-4 text-sm">
          {paying ? 'Saving…' : 'Mark as Paid'}
        </Button>
      )}
```
Change the `else` branch so the button only renders when `onPay` is provided:
```jsx
      {settlement.is_paid ? (
        <span className="flex items-center gap-1 rounded-pill border border-emerald-400/40 bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Paid
        </span>
      ) : onPay ? (
        <Button
          onClick={onPay}
          disabled={paying}
          className="shrink-0 px-4 text-sm"
        >
          {paying ? 'Saving…' : 'Mark as Paid'}
        </Button>
      ) : null}
```
(Keep the rest of the component unchanged.)

- [ ] **Step 2: SettlementPage — single Confirm & settle**

Rewrite `frontend/src/pages/SettlementPage.jsx` to drop per-pair paying and add one confirm. Read the current file first, then make it:
```jsx
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import SettlementItem from '../components/SettlementItem';

export default function SettlementPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { data } = await api.get(`/groups/${id}/settlements/`);
      setBalances(data.balances);
      setSettlements(data.settlements);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load settlements');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConfirm = async () => {
    setConfirming(true);
    setError('');
    try {
      await api.post(`/groups/${id}/settlements/confirm`);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to settle');
      setConfirming(false);
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-semibold text-white">Settle Up</h1>
        <Link
          to={`/groups/${id}`}
          className="text-sm font-medium text-sky-400 transition-colors hover:text-sky-300"
        >
          Back to group
        </Link>
      </div>

      <ErrorMessage message={error} />

      <div className="glass p-5">
        <h2 className="text-[13px] font-medium uppercase tracking-wide text-white/50">
          Balances
        </h2>
        <div className="mt-3 space-y-2">
          {balances.map((b) => (
            <div
              key={b.user_id}
              className="flex items-center justify-between text-[15px]"
            >
              <span className="text-white/75">{b.username || 'Unknown'}</span>
              <span
                className={`font-semibold tabular-nums ${
                  b.balance > 0.004
                    ? 'text-emerald-400'
                    : b.balance < -0.004
                      ? 'text-red-400'
                      : 'text-white/30'
                }`}
              >
                {b.balance > 0.004 ? '+' : ''}
                ${b.balance.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <h2 className="text-lg font-medium text-white/90">Who pays whom</h2>
      {settlements.length === 0 ? (
        <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
          <p className="text-[15px] text-white/55">
            All even — nobody owes anything.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {settlements.map((settlement, i) => (
            <SettlementItem
              key={settlement.id}
              settlement={settlement}
              style={{ animationDelay: `${i * 50}ms` }}
              paying={false}
              onPay={null}
            />
          ))}
        </div>
      )}

      <Button
        variant="primary"
        className="w-full"
        onClick={handleConfirm}
        disabled={confirming}
      >
        {confirming ? 'Settling…' : 'Confirm & settle'}
      </Button>
    </div>
  );
}
```

- [ ] **Step 3: Build** — `cd frontend && npm run build` → no errors.

- [ ] **Step 4: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add frontend/src/components/SettlementItem.jsx frontend/src/pages/SettlementPage.jsx
git commit -m "feat: single confirm-and-settle on settlement page"
```

---

## Task 7: Payment History on the home page

**Files:** Create `frontend/src/components/PaymentHistoryItem.jsx`; modify `frontend/src/pages/HomePage.jsx`.

- [ ] **Step 1: Create `frontend/src/components/PaymentHistoryItem.jsx`**
```jsx
import { useState } from 'react';
import api from '../api/axios';
import SettlementItem from './SettlementItem';

export default function PaymentHistoryItem({ group, canDelete, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      try {
        const [expensesRes, settleRes] = await Promise.all([
          api.get(`/groups/${group.id}/expenses/`),
          api.get(`/groups/${group.id}/settlements/`),
        ]);
        setDetail({
          expenses: expensesRes.data,
          settlements: settleRes.data.paid_settlements ?? [],
        });
      } catch {
        setDetail({ expenses: [], settlements: [] });
      } finally {
        setLoading(false);
      }
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!window.confirm('Remove this from payment history?')) return;
    setDeleting(true);
    try {
      await api.delete(`/groups/${group.id}`);
      onDeleted(group.id);
    } catch {
      setDeleting(false);
    }
  };

  return (
    <div className="glass overflow-hidden">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div>
          <p className="text-[15px] font-semibold text-white">{group.name}</p>
          <p className="text-[13px] text-white/50">
            Settled {new Date(group.settled_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold tabular-nums text-white/70">
            ${(group.total ?? 0).toFixed(2)}
          </span>
          <span className="text-white/40">{open ? '▾' : '▸'}</span>
        </div>
      </button>

      {open && (
        <div className="space-y-4 border-t border-white/10 p-4">
          {loading || !detail ? (
            <p className="text-[14px] text-white/50">Loading…</p>
          ) : (
            <>
              <div>
                <h4 className="text-[12px] font-medium uppercase tracking-wide text-white/45">
                  Expenses
                </h4>
                <div className="mt-2 space-y-1">
                  {detail.expenses.map((e) => (
                    <div
                      key={e.id}
                      className="flex items-center justify-between text-[14px]"
                    >
                      <span className="text-white/75">
                        {e.title}
                        <span className="text-white/40">
                          {' '}· {e.paid_by_username || 'Someone'}
                        </span>
                      </span>
                      <span className="tabular-nums text-white/70">
                        ${e.amount.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {detail.settlements.length > 0 && (
                <div>
                  <h4 className="text-[12px] font-medium uppercase tracking-wide text-white/45">
                    Settlement
                  </h4>
                  <div className="mt-2 space-y-2">
                    {detail.settlements.map((s) => (
                      <SettlementItem
                        key={s.id}
                        settlement={s}
                        paying={false}
                        onPay={null}
                      />
                    ))}
                  </div>
                </div>
              )}

              {canDelete && (
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="text-[13px] font-medium text-red-400/80 transition-colors hover:text-red-400 disabled:opacity-40"
                >
                  {deleting ? 'Removing…' : 'Remove from history'}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: HomePage — split active vs history**

In `frontend/src/pages/HomePage.jsx`: import `useAuthStore` and `PaymentHistoryItem`, then split `groups` into active and settled and render a Payment History section. Add imports:
```jsx
import useAuthStore from '../store/authStore';
import PaymentHistoryItem from '../components/PaymentHistoryItem';
```
Add inside the component (after the `useState`s):
```jsx
  const user = useAuthStore((s) => s.user);
```
Replace the groups list render block (the `groups.length === 0 ... groups.map(...)` section) with active/history split. Specifically, compute before `return`:
```jsx
  const activeGroups = groups.filter((g) => !g.settled_at);
  const settledGroups = groups.filter((g) => g.settled_at);
```
Render active groups using `GroupCard` (as today, but mapping `activeGroups`), then add this Payment History section after the active list and before the "Join a group" block:
```jsx
      {settledGroups.length > 0 && (
        <div className="space-y-3 pt-2">
          <h2 className="text-lg font-medium text-white/90">Payment History</h2>
          {settledGroups.map((group) => (
            <PaymentHistoryItem
              key={group.id}
              group={group}
              canDelete={group.created_by === user?.id}
              onDeleted={(gid) =>
                setGroups((prev) => prev.filter((g) => g.id !== gid))
              }
            />
          ))}
        </div>
      )}
```
Also update the empty-state condition to use `activeGroups` (so an empty active list still shows the prompt while history may exist): change `groups.length === 0 && !error` to `activeGroups.length === 0 && !error` and map `activeGroups` instead of `groups` in the `GroupCard` list.

- [ ] **Step 3: Build** — `cd frontend && npm run build` → no errors.

- [ ] **Step 4: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add frontend/src/components/PaymentHistoryItem.jsx frontend/src/pages/HomePage.jsx
git commit -m "feat: payment history section on home page"
```

---

## Task 8: GroupDetailPage — read-only when settled

**Files:** Modify `frontend/src/pages/GroupDetailPage.jsx`.

- [ ] **Step 1: Guard settled groups**

In `frontend/src/pages/GroupDetailPage.jsx`, after `const isCreator = ...` (or near the top of the render), compute:
```jsx
  const isSettled = Boolean(group.settled_at);
```
Then:
- Wrap the "Settle Up" `<Link>` block so it only renders when `!isSettled`:
```jsx
      {!isSettled && (
        <Link to={`/groups/${id}/settle`} className="block">
          <Button variant="primary" className="mt-2 w-full">
            Settle Up
          </Button>
        </Link>
      )}
```
- Wrap the floating add-expense `<Link className="fab">` so it only renders when `!isSettled`.
- When `isSettled`, show a small note above the expenses list:
```jsx
      {isSettled && (
        <div className="rounded-glass border border-emerald-400/30 bg-emerald-500/10 p-3 text-center text-[14px] text-emerald-300">
          Settled — this group is archived in Payment History.
        </div>
      )}
```
Also hide the per-expense delete control when settled: where `ExpenseItem` is given `canDelete={...}`, change it to `canDelete={!isSettled && (expense.created_by === user?.id || isCreator)}`.

- [ ] **Step 2: Build** — `cd frontend && npm run build` → no errors.

- [ ] **Step 3: Manual verification (full feature)** — with backend + frontend running, logged in (code `000000`):
  1. Create a group, add expenses, Settle Up → see "Who pays whom" → **Confirm & settle** → lands on Home.
  2. The group is gone from "My Groups" and appears under **Payment History**; expand it to see expenses + settlement.
  3. Open the settled group via history; confirm you cannot add/delete expenses or re-settle.
  4. As creator, expand a history entry and **Remove from history** → it disappears (soft delete) and stays gone after refresh.

- [ ] **Step 4: Commit**
```bash
cd /Users/chunchenglee/Desktop/Projects/settlo
git add frontend/src/pages/GroupDetailPage.jsx
git commit -m "feat: make settled groups read-only in group detail"
```

---

## Final verification
- [ ] `cd backend && DEV_OTP_CODE= python -m unittest discover -s tests` → OK.
- [ ] `cd frontend && npm run build` → clean.
- [ ] Manual end-to-end (Task 8 Step 3) passes.
- [ ] `git status`: only `backend/app/core/config.py` + `backend/app/services/otp.py` remain modified (local OTP bypass); `backend/.env` untracked.
- [ ] When ready: `git push -u origin feat/settle-archive-history` and open a PR.
