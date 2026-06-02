import asyncio
from dotenv import load_dotenv
from pymongo import MongoClient
from pydantic import field_validator
import os
import yosoi as ys

load_dotenv()

# MongoDB setup
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["transit_aggregator"]
collection = db["articles"]

# Custom contract since listing pages don't have full body text
class TransitArticle(ys.Contract):
    headline: str = ys.Title(description="Article, announcement, or project title")
    author: str | None = ys.Author(default=None)
    date: str | None = ys.Field(default=None, description="Publication date or project completion date")
    url: str | None = ys.Url(default=None, description="URL href attribute of the link to the full article or project page — use ::attr(href) to extract the href, not the link text")

    @field_validator('url', mode='before')
    @classmethod
    def reject_non_urls(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith('http'):
            return None
        return v

SOURCES = [
    {"url": "https://ridecarta.com/news-announcements/", "city": "Charleston", "agency": "CARTA", "force_simple": True},
    {"url": "https://www.newsbreak.com/charleston-sc-traffic", "city": "Charleston", "agency": "NewsBreak Charleston"},
    {"url": "https://www.metro.net/projects-listing/", "city": "Los Angeles", "agency": "LA Metro"},
    {"url": "https://www.amny.com/nyc-transit/", "city": "New York", "agency": "amNY"},
]

async def scrape_source(source: dict) -> None:
    config = ys.auto_config()
    pipeline = ys.Pipeline(llm_config=config, contract=TransitArticle)

    from yosoi.core.fetcher import create_fetcher

    print(f"Scraping {source['agency']}...")
    fetcher_type = 'simple' if source.get('force_simple') else 'waterfall'
    async with create_fetcher(fetcher_type) as fetcher:
        async for item in pipeline.scrape(source["url"], fetcher=fetcher):
            if not item.get("headline"):
                print("  Skipped: no headline")
                continue

            item["city"] = source["city"]
            item["agency"] = source["agency"]
            item["source_url"] = source["url"]

            if not collection.find_one({"headline": item.get("headline"), "agency": item["agency"]}):
                collection.insert_one(item)
                item.pop("_id", None)
                print(f"  Saved: {item.get('headline')}")
            else:
                print(f"  Skipped (duplicate): {item.get('headline')}")

async def main() -> None:
    for source in SOURCES:
        await scrape_source(source)
    print("\nDone! Check your MongoDB Atlas collection.")

if __name__ == "__main__":
    asyncio.run(main())
