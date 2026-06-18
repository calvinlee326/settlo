# Settlo — Better Group Joining

Date: 2026-06-17
Branch: `feat/friends-direct-expenses` (builds on the unmerged friends feature)

## Goal

Replace "long token / invite link only" group joining with four better paths,
keeping the existing invite link working as a fallback:

1. **Invite friends directly** — add accepted friends to a group with one tap (auto-join, no link).
2. **Short join code** — a 6-char human-friendly code instead of a 16-char token.
3. **QR code** — scan-to-join on the group page.
4. **Invite by phone** — send a pending group invite the recipient accepts (for non-friends).

## Shared refactor (do first)

`join_group` (`groups.py`) currently does: capacity check → add `Membership` →
re-split EQUAL expenses across the new member set when unsettled. Every new join
path must do the same. Extract:

```
_add_member(db, group, user_id) -> None
```

Behavior: if already a member, return (idempotent). Else: block if
`group.settled_at is not None` (400 "Group is already settled"); block if at
`max_members` (400 "Group is full"); add `Membership`; flush; re-split every
EQUAL expense via the existing `equal_split` over the full member set.

`join_group` becomes: resolve group by token (404) → `_add_member(db, group,
current_user.id)` → commit → return detail. **Behavior change:** joining a
*settled* group is now blocked (was silently allowed); consistent with
settled = read-only.

## 1. Invite friends directly

- `POST /api/groups/{group_id}/members` body `{user_id}`. Caller must be a member;
  `user_id` must be an **accepted friend of the caller** (`friends_svc.are_friends`)
  else 403; then `_add_member`. Returns `GroupDetail`.
- Schema `AddMemberRequest{user_id: str}`.
- Frontend: in `GroupDetailPage`, an "Add friends" section listing the caller's
  accepted friends who are not already members; tap adds them and reloads.

## 2. Short join code

- New `_generate_code()` → 6 chars from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`
  (no ambiguous `0/O/1/I/L`). `_unique_invite_code(db)` retries (≤10) against the
  existing unique `invite_token` column. `create_group` sets
  `invite_token=_unique_invite_code(db)` explicitly.
- Existing groups keep their long tokens; lookups are exact-match so both work.
- Frontend: show the code prominently on `GroupDetailPage`. The Home join box
  already accepts a bare token, so a code works unchanged.

## 3. QR code

- Add dependency `qrcode.react`. In the `GroupDetailPage` invite modal, render
  `<QRCodeSVG value={inviteLink} />` alongside the code. Scanning opens the
  existing `/invite/:token` flow.

## 4. Invite by phone

- New model `GroupInvitation`: `id, group_id (FK), invited_user_id (FK users),
  invited_by (FK users), status (PENDING|ACCEPTED), created_at, responded_at`.
  Unique `(group_id, invited_user_id)`. Migration `0005`.
- New router `group_invitations` (prefix `/api/group-invitations`, separate
  prefix to avoid `/{group_id}` path collisions); imports `_add_member`,
  `get_group_or_404`, `require_membership` from `groups`.
  - `POST /api/group-invitations` `{group_id, phone_number}` — caller is a member
    of the group; resolve phone→user (404 if none); reject self, already-member
    (400), and existing pending invite (400); create PENDING.
  - `GET /api/group-invitations` — my pending invites (`invited_user_id == me`,
    PENDING) with group name + inviter username.
  - `POST /api/group-invitations/{id}/accept` — addressee-only; `_add_member`;
    set ACCEPTED + `responded_at`.
  - `POST /api/group-invitations/{id}/decline` — addressee-only; delete.
- Schemas `GroupInviteCreate{group_id, phone_number}`,
  `GroupInvitationOut{id, group_id, group_name, invited_by_username, created_at}`.
- Frontend: an "Invite by phone" input on `GroupDetailPage` (reusing the
  `+1` phone normalization); a pending group-invites section on `HomePage` with
  accept/decline; a red badge on the Navbar "Settlo"/home link counting pending
  group invites (polled, same pattern as the friend-request badge).

## Guards / invariants

- All new endpoints depend on `get_current_user`.
- Money: EQUAL re-split uses the existing `equal_split` (Decimal/CENT) — never reimplemented.
- Default-deny: add-member requires friendship; invite create requires caller
  membership; accept/decline are addressee-only; phone lookup is exact-match on
  the stored `+1XXXXXXXXXX`.
- Capacity (`max_members`) and settled-state are enforced centrally in `_add_member`.

## Known simplifications

- Invite-friends auto-joins (friends are already trusted); only the phone path is
  an accept flow.
- Short code space ≈ 30^6 (~729M) with a unique constraint + retry; collisions are
  astronomically unlikely.
- `qrcode.react` is the one new frontend dependency.

## Rollout order

2 (short code) → 3 (QR) → 1 (friends-direct) → 4 (phone invite), cheapest first,
after the shared `_add_member` refactor.
