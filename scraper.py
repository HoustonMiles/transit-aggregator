import asyncio
import time
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import yosoi as ys
from yosoi.core.fetcher import create_fetcher
from pydantic import field_validator

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["transit_aggregator"]
collection = db["articles"]

class TransitArticle(ys.Contract):
    headline: str = ys.Title(description="Article, announcement, or project title")
    author: str | None = ys.Author(default=None)
    date: str | None = ys.Field(default=None, description="Publication date or project completion date")
    url: str | None = ys.Url(default=None, description="The href attribute of the link to the full article, e.g. 'https://...'")

    @field_validator('url', mode='before')
    @classmethod
    def reject_non_urls(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith('http'):
            return None
        return v

SOURCES = [
    {"url": "https://ridecarta.com/news-announcements/", "city": "Charleston", "agency": "CARTA", "fetcher_type": "simple"},
    {"url": "https://www.newsbreak.com/charleston-sc-traffic", "city": "Charleston", "agency": "NewsBreak Charleston", "fetcher_type": "waterfall"},
    {"url": "https://www.metro.net/about_categories/news-releases/", "city": "Los Angeles", "agency": "LA Metro", "fetcher_type": "waterfall"},
    {"url": "https://www.amny.com/nyc-transit/", "city": "New York", "agency": "amNY", "fetcher_type": "waterfall"},
]

async def scrape_source(source: dict) -> dict:
    """Scrape one source and return stats for logging."""
    start = time.monotonic()
    config = ys.auto_config()
    pipeline = ys.Pipeline(llm_config=config, contract=TransitArticle)

    saved = 0
    skipped_dup = 0
    skipped_no_headline = 0
    error = None

    print(f"Scraping {source['agency']}...")
    try:
        async with create_fetcher(source.get("fetcher_type", "waterfall")) as fetcher:
            async def _run():
                nonlocal saved, skipped_dup, skipped_no_headline
                async for item in pipeline.scrape(source["url"], fetcher=fetcher):
                    if not item.get("headline"):
                        skipped_no_headline += 1
                        continue

                    item["city"] = source["city"]
                    item["agency"] = source["agency"]
                    item["source_url"] = source["url"]

                    if not collection.find_one({"headline": item.get("headline"), "agency": item["agency"]}):
                        collection.insert_one(item)
                        item.pop("_id", None)
                        saved += 1
                        print(f"  Saved: {item.get('headline')}")
                    else:
                        skipped_dup += 1

            await asyncio.wait_for(_run(), timeout=120)  # 2 minute cap per source
    except asyncio.TimeoutError:
        error = "Timed out after 120s"
        print(f"  {error}")
    except Exception as e:
        error = str(e)
        print(f"  Error: {error}")

    elapsed = time.monotonic() - start
    return {
        "agency": source["agency"],
        "city": source["city"],
        "saved": saved,
        "skipped_duplicates": skipped_dup,
        "skipped_no_headline": skipped_no_headline,
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
    }

async def main() -> None:
    run_start = datetime.now(timezone.utc)
    results = []

    for source in SOURCES:
        result = await scrape_source(source)
        results.append(result)

    run_log = {
        "timestamp": run_start.isoformat(),
        "total_articles_in_db": collection.count_documents({}),
        "sources": results,
    }

    # Append to a JSONL log file - one JSON object per line
    with open("run_log.jsonl", "a") as f:
        f.write(json.dumps(run_log) + "\n")

    print("\nDone! Run summary:")
    for r in results:
        print(f"  {r['agency']}: {r['saved']} saved, {r['skipped_duplicates']} dupes, {r['elapsed_seconds']}s")
    print(f"\nTotal in DB: {run_log['total_articles_in_db']}")

if __name__ == "__main__":
    asyncio.run(main())
