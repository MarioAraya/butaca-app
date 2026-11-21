import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.api.router import router
from src.config import settings
from src.db.engine import SessionLocal
from src.db.migrations import create_tables
from src.db.models import ScrapeLog
from src.scraper.orchestrator import run_scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _should_scrape_on_startup() -> bool:
    today = datetime.now(timezone.utc).date()
    with SessionLocal() as db:
        last_success = (
            db.query(ScrapeLog)
            .filter(ScrapeLog.status.in_(("success", "partial")))
            .order_by(ScrapeLog.id.desc())
            .first()
        )
        if last_success is None or last_success.finished_at is None:
            return True
        return last_success.finished_at.date() < today


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    logger.info("Database tables created")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scrape,
        trigger=CronTrigger(hour=settings.scrape_cron_hour, minute=settings.scrape_cron_minute),
        id="daily_scrape",
        name="Daily Cinepolis scrape",
    )
    scheduler.start()
    logger.info("Scheduler started: daily scrape at %02d:%02d", settings.scrape_cron_hour, settings.scrape_cron_minute)

    if _should_scrape_on_startup():
        logger.info("No successful scrape today, triggering startup scrape")
        asyncio.create_task(run_scrape())
    else:
        logger.info("Skipping startup scrape: already ran successfully today")

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="que-ver-cine-hoy",
    description="API de cartelera de Cinepolis Chile",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# /billboard returns the whole listing (~270 KB of JSON); compresses ~10x
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    client = request.client.host if request.client else "-"
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("%s %s failed after %.1fms client=%s", request.method, request.url.path, duration_ms, client)
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(
        level,
        "%s %s %d %.1fms client=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        client,
    )
    return response


app.include_router(router)
