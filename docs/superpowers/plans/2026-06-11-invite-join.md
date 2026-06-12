# Invite Link Popup + Join Group Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix invite link generation on non-HTTPS devices and add a "Join a group" input on the home page.

**Architecture:** Remove the server-built invite URL from the backend response; the frontend constructs it using `window.location.origin`. Replace the clipboard-only invite flow with a modal popup. Add a join-by-link input on the home page.

**Tech Stack:** FastAPI (Python), React + Vite, Tailwind CSS

---

### Task 1: Remove `invite_link` from backend schema and router

**Files:**
- Modify: `backend/app/schemas/group.py:38-41`
- Modify: `backend/app/routers/groups.py:231-241`

- [ ] **Step 1: Update `InviteOut` schema**

In `backend/app/schemas/group.py`, replace lines 38-41:

```python
class InviteOut(BaseModel):
    invite_token: str
```

- [ ] **Step 2: Update the router to return only the token**

In `backend/app/routers/groups.py`, replace lines 239-242:

```python
    return InviteOut(invite_token=group.invite_token)
```

Also remove the `settings` import usage from that return — the `settings.FRONTEND_URL` reference is no longer needed in this function. The import at the top of the file can stay (it's used elsewhere).

- [ ] **Step 3: Verify backend starts without error**

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected: `Application startup complete.` with no traceback.

- [ ] **Step 4: Smoke-test the endpoint**

With the backend running and a valid group ID, hit:
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/groups/<group_id>/invite
```
Expected JSON: `{"invite_token": "..."}` — no `invite_link` field.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/group.py backend/app/routers/groups.py
git commit -m "feat: return only invite_token from invite endpoint, build URL client-side"
```

---

### Task 2: Replace clipboard invite with modal popup in GroupDetailPage

**Files:**
- Modify: `frontend/src/pages/GroupDetailPage.jsx`

- [ ] **Step 1: Add `inviteLink` state and update `handleInvite`**

In `GroupDetailPage.jsx`, add one state variable and rewrite `handleInvite`:

```jsx
const [inviteLink, setInviteLink] = useState('');

const handleInvite = async () => {
  try {
    const { data } = await api.get(`/groups/${id}/invite`);
    setInviteLink(
      `${window.location.origin}/invite/${data.invite_token}`
    );
  } catch (err) {
    setError(err.response?.data?.detail || 'Failed to get invite link');
  }
};
```

Remove the old `inviteCopied` state and its `setTimeout` logic — no longer needed.

- [ ] **Step 2: Add copy handler with fallback**

Add this function inside the component, below `handleInvite`:

```jsx
const [copied, setCopied] = useState(false);

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(inviteLink);
  } catch {
    const el = document.createElement('textarea');
    el.value = inviteLink;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
  }
  setCopied(true);
  setTimeout(() => setCopied(false), 2000);
};
```

- [ ] **Step 3: Add the modal JSX**

Add this block just before the closing `</div>` of the component's return:

```jsx
{inviteLink && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
    <div className="glass-strong w-full max-w-sm space-y-4 p-6">
      <h2 className="text-[17px] font-semibold text-white">Invite Link</h2>
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
          {copied ? 'Copied!' : 'Copy'}
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

- [ ] **Step 4: Remove stale `inviteCopied` JSX**

In the member avatar row, find and remove:

```jsx
{inviteCopied && (
  <span className="text-xs font-medium text-emerald-400">
    Invite link copied!
  </span>
)}
```

- [ ] **Step 5: Verify in browser**

Open a group on both Mac (`localhost:5173`) and phone (`192.168.1.173:5173`). Tap the `+` avatar button. Modal should appear with the correct full URL. Copy button should work on both devices.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/GroupDetailPage.jsx
git commit -m "feat: show invite link in modal popup instead of clipboard-only"
```

---

### Task 3: Add "Join a group" input on HomePage

**Files:**
- Modify: `frontend/src/pages/HomePage.jsx`

- [ ] **Step 1: Add join state and handler**

Add inside `HomePage`:

```jsx
const navigate = useNavigate();
const [joinInput, setJoinInput] = useState('');

const handleJoin = () => {
  const val = joinInput.trim();
  if (!val) return;
  let token = val;
  try {
    const url = new URL(val);
    const parts = url.pathname.split('/').filter(Boolean);
    token = parts[parts.length - 1];
  } catch {
    // not a URL, treat as bare token
  }
  navigate(`/invite/${token}`);
};
```

Add `useNavigate` to the import from `react-router-dom`:

```jsx
import { Link, useNavigate } from 'react-router-dom';
```

- [ ] **Step 2: Add the join section JSX**

Add this block after the group list (before the `<Link to="/groups/new">` FAB):

```jsx
<div className="glass p-4 space-y-3">
  <p className="text-[13px] font-medium text-white/55">Join a group</p>
  <div className="flex gap-2">
    <input
      type="text"
      placeholder="Paste invite link or token"
      value={joinInput}
      onChange={(e) => setJoinInput(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && handleJoin()}
      className="min-w-0 flex-1 rounded-xl bg-white/10 px-3 py-2 text-[14px] text-white placeholder-white/30 outline-none"
    />
    <button
      onClick={handleJoin}
      className="shrink-0 rounded-xl bg-violet-500 px-4 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
      disabled={!joinInput.trim()}
    >
      Join
    </button>
  </div>
</div>
```

- [ ] **Step 3: Verify in browser**

On the home page, paste a full invite URL (e.g. `http://192.168.1.173:5173/invite/abc123`) into the input and tap Join. Should navigate to `/invite/abc123`. Also test with a bare token (`abc123`) — should navigate to `/invite/abc123`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.jsx
git commit -m "feat: add join-by-invite-link input on home page"
```
