# Settle & Archive to Payment History — Design

**Date:** 2026-06-15
**Status:** Approved (design)

## Problem / pivot

The earlier "settlement rounds" feature was reverted. The desired model is simpler: a group is
used **once**. You add expenses, press **Settle Up** to see who owes whom, press **Confirm**,
and the whole group (expenses + the settlement detail) is **archived into Payment History** on
the main page. Payment History is a separate, expandable section. Next time you create a new
group.

## Decisions (confirmed with user)

- **One-time groups.** Confirming a settle-up **archives the whole group**; it leaves the active
  list and appears under Payment History.
- **Single confirm**, not per-payment marking. Confirm records the agreed who-owes-whom as a
  fact (no per-person "mark as paid" checklist afterward).
- **Payment History** lives as a **separate, collapsible section on the main (home) page**; each
  entry expands to show that group's expenses and settlement detail.
- **Soft delete:** deleting a settled group from history sets a `deleted_at` flag (hidden, kept
  in the DB), it is not hard-deleted.
- **No rounds.** All rounds code was reverted; this design starts from the original version.

## Data model + migration

`groups` table — add three nullable columns:
- `settled_at` (DateTime, nullable) — `NULL` = active; set = archived/settled.
- `settled_by` (String(36) FK users.id, nullable) — who confirmed.
- `deleted_at` (DateTime, nullable) — `NULL` = visible; set = soft-deleted.

New Alembic migration `0002` adds these three columns (all default `NULL`, so existing groups
stay active and visible). The ORM `Group` model gains the matching `Mapped[... | None]` columns.

## Backend

- **`get_group_or_404`** excludes soft-deleted groups (treat `deleted_at IS NOT NULL` as 404).
- **`list_my_groups` (`GET /groups/`)**: returns the user's groups with `deleted_at IS NULL`
  (both active and settled), now including `settled_at` and a computed `total` (sum of the
  group's expense amounts, via one batched grouped query — no N+1). The frontend splits active
  (`settled_at` null) from history (`settled_at` set).
- **`POST /api/groups/{group_id}/settlements/confirm`** (lives in `settlements.py` to avoid a
  circular import with `groups.py`): any member; rejects if the group is already settled
  (`400 "Group is already settled"`) or has no expenses (`400 "Add an expense before settling"`).
  Computes balances + the settlement plan, persists each transaction as a paid `Settlement`
  row (`is_paid=True`, `paid_at=now`), and stamps `group.settled_at`/`settled_by`. Returns the
  updated `SettlementResult` (balances now ~0, the stored settlements under `paid_settlements`).
  A plan with zero transactions (everyone already even) still archives the group.
- **Expense mutations blocked once settled:** `create_expense` and `delete_expense` reject with
  `400 "Group is already settled"` when `group.settled_at` is set.
- **`delete_group` becomes a soft delete:** sets `group.deleted_at = now` (creator only, as
  today) instead of hard-deleting rows. All group queries filter `deleted_at IS NULL`.
- `get_settlements` is unchanged and serves both phases: active group → balances + draft plan;
  settled group → balances ~0 + the stored settlements under `paid_settlements`.
- `GroupOut`/`GroupDetail` schemas gain `settled_at: datetime | None` and `total: float = 0`.

## Frontend

- **HomePage:** one `GET /groups/` call, split client-side:
  - **"My Groups"** — entries with `settled_at == null` (existing `GroupCard`).
  - **"Payment History"** — a separate, collapsible section listing entries with `settled_at`
    set. Each entry is a `PaymentHistoryItem` that expands to show the group's expenses and
    settlement detail (lazy-fetched on expand via the existing `GET /groups/{id}/expenses/`
    and `GET /groups/{id}/settlements/`), plus a soft-delete control (creator only).
- **GroupDetailPage:** active groups only — add expenses + a **Settle Up** link. If the group is
  already settled, show a read-only note and hide the add-expense / settle controls.
- **SettlementPage:** shows balances + who-owes-whom, and a single **"Confirm & settle"** button
  (replaces the per-pair "Mark as Paid"). On confirm → `POST .../settlements/confirm` →
  navigate home → the group now appears under Payment History.

## Error handling

- Confirm on an already-settled group → `400`. Confirm on an empty group → `400`. UI hides the
  Confirm button when there are no expenses and after settling.
- Expense add/delete on a settled group → `400` (UI hides those controls).
- Soft-deleted and (for `get_group_or_404`) settled-but-still-readable groups handled explicitly.

## Testing (backend, `unittest` against in-memory SQLite, `DEV_OTP_CODE=` prefix)

- Confirm archives: creates paid `Settlement` rows for the plan, sets `settled_at`/`settled_by`,
  and a follow-up `get_settlements` shows balances ~0 with the stored settlements.
- Confirm rejects when already settled, and when no expenses.
- Confirm with zero-debt expenses still archives (no settlement rows, `settled_at` set).
- `create_expense`/`delete_expense` rejected once settled.
- `list_my_groups` excludes soft-deleted, includes settled, reports correct `total`.
- `delete_group` soft-deletes (row remains, `deleted_at` set, no longer listed).

## Out of scope

- Per-person payment tracking after confirm; reopening a settled group; real-time sync; hard
  delete; editing a settled group.
