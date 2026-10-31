from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import errors, middleware
from .config import get_settings
from .db import create_indexes, get_db
from .routes import ai, merchant, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await create_indexes(db)
    if get_settings().mongo_uri == "memory" and not await db.merchants.find_one({}):
        from .seed import seed  # in-memory DB starts empty every run
        await seed(db)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Dukan Dost API", version="0.1.0", lifespan=lifespan)
    errors.install(app)
    middleware.install(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=[o.strip() for o in s.web_origin.split(",")],
        # phones on the LAN / tunnels during the demo
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?|https://.*\.trycloudflare\.com",
        allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "Retry-After"])
    app.include_router(merchant.router)
    app.include_router(ai.router)
    app.include_router(public.router)
    return app


app = create_app()
