import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import auth, direct_expenses, expenses, friends, group_invitations, groups, rates, settlements
from app.services.fx import RatesUnavailable

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
