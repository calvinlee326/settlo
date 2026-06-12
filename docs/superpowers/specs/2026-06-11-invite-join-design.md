# Invite Link Popup + Join Group Input

**Date:** 2026-06-11

## Problem

1. `navigator.clipboard.writeText()` is blocked on non-HTTPS (LAN phone access), so invite generation silently fails.
2. Backend builds invite link using `FRONTEND_URL` (localhost), so the link is wrong when accessed from a phone.
3. No UI for an existing logged-in user to join a group via a pasted link.

## Changes

### Backend — `GET /groups/{id}/invite`

- Remove `invite_link` from the response. Return only `invite_token`.
- Frontend constructs the full URL as `window.location.origin + "/invite/" + token`.

### Frontend — GroupDetailPage (invite popup)

- `handleInvite` fetches the token, builds the full link, and sets `inviteLink` state.
- A modal overlay renders when `inviteLink` is set: readonly input showing the link, Copy button, Close button.
- Copy button: tries `navigator.clipboard.writeText()`, falls back to `document.execCommand('copy')`.

### Frontend — HomePage (join input)

- Below the group list: a text input + Join button.
- Accepts a full URL (`http://…/invite/abc123`) or bare token (`abc123`).
- On submit: extract the token (last path segment if URL, raw value if not), navigate to `/invite/:token`.
- No backend call on this step — InvitePage handles validation.

## Out of scope

- QR codes
- Native share sheet
- Invite link expiry or revocation
