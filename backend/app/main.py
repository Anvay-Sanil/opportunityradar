import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.database import engine
from app.models.base import Base
from sqlalchemy import text
from app.routes import (
    auth_router,
    opportunities_router,
    applications_router,
    digest_router,
    profile_router,
    admin_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
schema_lock = asyncio.Lock()


async def initialize_schema():
    async with schema_lock:
        if not app.state.schema_ready:
            if settings.auto_create_tables:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            app.state.schema_ready = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpportunityRadar...")
    try:
        await asyncio.wait_for(initialize_schema(), timeout=10)
    except Exception:
        logger.exception("Database initialization failed; readiness will retry when it recovers")
    yield
    await engine.dispose()
    from app.routes.opportunities import ranking_engine
    await ranking_engine.aclose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="OpportunityRadar API",
    description="Smart internship aggregator for students",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.state.schema_ready = False
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(opportunities_router)
app.include_router(applications_router)
app.include_router(digest_router)
app.include_router(admin_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}


@app.get("/api/ready")
async def ready():
    async def check_database():
        await initialize_schema()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(check_database(), timeout=10)
    except Exception:
        logger.exception("Database readiness check failed")
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "Database unavailable"})
    return {"status": "ready"}
