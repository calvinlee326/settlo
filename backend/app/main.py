import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401,F403 — register all tables with Base
from app.routers import auth, expenses, groups, settlements

logging.basicConfig(level=logging.INFO)

# Dev convenience; Alembic manages schema changes in production
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Settlo", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(settlements.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
