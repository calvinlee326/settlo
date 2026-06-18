# Settlo — Friends + Direct Expenses

Date: 2026-06-17
Branch: `feat/friends-direct-expenses`

## Goal

Let users connect as friends (mutual request/accept) and split expenses with one
or more friends **without creating a group**. Friend balances roll up per-pair
(Splitwise style): one net number per friend across all shared direct expenses.

## Non-goals

- Multi-currency netting (single currency per the existing group assumption).
- Auto-creating friendships from shared direct expenses.
- Quick-adding friends into formal groups (deferred; can build later).

## Data model

### New `friendships` table
| column | type | notes |
|---|---|---|
| id | str(36) PK | uuid |
| requester_id | str(36) FK users.id | who sent the request |
| addressee_id | str(36) FK users.id | who receives it |
| status | enum(PENDING, ACCEPTED) | declined rows are deleted, not stored |
| created_at | datetime | |
| responded_at | datetime nullable | set on accept |

- Unique constraint on `(requester_id, addressee_id)`.
- Friendship is logically undirected: a lookup for "are A and B friends" checks
  both `(A,B)` and `(B,A)`. Only one row exists per pair (creation is blocked if a
  row exists in either direction).

### Expense / Settlement changes
- `expenses.group_id` → **nullable**.
- `settlements.group_id` → **nullable**.
- A row with `group_id = NULL` is a *direct* (friend) expense/settlement.
- Direct-expense participants are defined entirely by `paid_by` + the
  `ExpenseSplit` rows. No new expense/split tables.

Alembic migration: create `friendships`; alter the two `group_id` columns to
nullable.

## API

All endpoints require auth (`get_current_user`).

### Friend requests
- `POST /api/friends/requests` `{phone_number}` → create PENDING.
  Checks: target user exists; not self; no friendship/pending in either
  direction. Returns the created request.
- `GET /api/friends/requests` → my incoming PENDING requests.
- `POST /api/friends/requests/{id}/accept` → set ACCEPTED, `responded_at=now`.
  Only the addressee may accept.
- `POST /api/friends/requests/{id}/decline` → delete the row. Only the addressee.
- `GET /api/friends` → my accepted friends, each with `net_balance`.
- `DELETE /api/friends/{friend_id}` → remove friendship. Blocked (400) if
  `net_balance != 0`.

### Direct expenses
- `POST /api/direct-expenses` `{paid_by, title, amount, currency, split_type, splits[]}`.
  **Trust boundary:** every participant (`paid_by` + each split `user_id`) must be
  an accepted friend of the caller, or the caller themselves. Reuses
  `_build_splits` with `member_ids` = the participant set.
- `GET /api/friends/{friend_id}/expenses` → direct expenses shared with that
  friend (both are participants).
- `DELETE /api/direct-expenses/{id}` → creator only.

### Settle up
- `POST /api/friends/{friend_id}/settle` → compute net, create
  `Settlement(group_id=NULL, from_user, to_user, amount, is_paid=True, paid_at=now)`
  in the direction that zeroes the balance. Mirrors the group settle-up flow.

## Balance math

Debt within a single expense is only between the payer and each other
participant. So for the caller `me` and a friend `friend`:

```
net(me, friend) =  Σ friend_share   over direct expenses I paid
                 − Σ my_share        over direct expenses friend paid
                 − Σ settlements I paid friend (is_paid)
                 + Σ settlements friend paid me (is_paid)
```

Positive = friend owes me. Computed live from existing tables; the pure
`calculate_settlements` / `equal_split` helpers in `services/settlement.py` are
reused unchanged. Expenses where neither `me` nor `friend` is the payer
contribute 0 to that pair.

## Frontend

- **FriendsPage** (new): accepted friends with net balances, an incoming-requests
  section (accept/decline), add-friend-by-phone form, and per-friend settle-up.
- Add a "Friends" entry to `Navbar`.
- Reuse `NewExpensePage` in a friend-scoped mode: participants are picked from the
  caller's friends instead of group members; posts to `/api/direct-expenses`.

## Tests

- Friendship: request, accept, decline, duplicate request rejected, self-request
  rejected.
- Direct expense with a non-friend participant → 403.
- Net-balance math including a 3-person direct expense (payer ↔ each ower).
- Settle-up records a settlement that zeroes the pair's net balance.

## Rollout

Two PRs against this branch (or sequential commits):
1. Friendships (model, migration, request/accept endpoints, FriendsPage list).
2. Direct expenses + balances + settle-up.

## Known simplifications

- Single currency for friend netting (defaults USD), matching today's group
  behavior. Multi-currency netting is out of scope.
- A 3-person direct expense does not create a friendship between the two
  non-creator participants; pairwise balances only surface where a friendship
  already exists.
