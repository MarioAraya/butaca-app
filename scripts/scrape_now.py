"""Manual scrape trigger for testing. Run with: python -m scripts.scrape_now"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from src.db.migrations import create_tables
from src.scraper.orchestrator import run_scrape


async def main():
    create_tables()
    await run_scrape()


if __name__ == "__main__":
    asyncio.run(main())
