import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.routers import auth, direct_expenses, expenses, friends, group_invitations, groups, rates, settlements
from app.services import changes
from app.services.fx import RatesUnavailable

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Settlo", version="1.0.0")

_origins = [settings.FRONTEND_URL]
if settings.EXTRA_ORIGINS:
    _origins += [o.strip() for o in settings.EXTRA_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(settlements.router)
app.include_router(friends.router)
app.include_router(direct_expenses.router)
app.include_router(group_invitations.router)
app.include_router(rates.router)


@app.exception_handler(RatesUnavailable)
def rates_unavailable(request: Request, exc: RatesUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.middleware("http")
async def announce_writes(request: Request, call_next):
    response = await call_next(request)
    # Sign-in, refresh and logout change nothing anyone else is looking at.
    if (
        request.method in WRITE_METHODS
        and response.status_code < 400
        and not request.url.path.startswith("/api/auth/")
    ):
        changes.bump()
    return response


def _signed_in_user_id(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> str:
    user_id = user.id
    # Hand the pooled connection back before the wait, or every open tab holds one.
    db.close()
    return user_id


@app.get("/api/changes")
async def wait_for_changes(seen: int | None = None, _: str = Depends(_signed_in_user_id)):
    return {"version": await changes.wait_for_change(seen)}


@app.get("/api/health")
def health():
    return {"status": "ok"}
