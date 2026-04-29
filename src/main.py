import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import router
from src.config import settings
from src.db.migrations import create_tables
from src.scraper.orchestrator import run_scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
app.include_router(router)
