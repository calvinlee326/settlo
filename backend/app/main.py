import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, expenses, friends, groups, settlements

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
