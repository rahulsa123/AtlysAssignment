import os
from http.client import HTTPException
from typing import Optional

from fastapi import FastAPI, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from cache.dict_cache import DictCache
from notification.console import ConsoleNotification
from scraper import Scraper
from storage.json_storage import JSONStorage

app = FastAPI()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable is not set")
api_key_header = APIKeyHeader(name="x-api-key")
cache = DictCache()


@app.get("/")
async def root():
    return {"message": "Hello World"}


class ScrapingInput(BaseModel):
    page_limit: Optional[int] = Field(default=10, ge=1, le=100)
    proxy: Optional[str] = None


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key


@app.post("/scrape")
async def scrape(scraping_input: ScrapingInput, api_key: str = Depends(get_api_key)):
    global cache  # using global cache to reduce image processing task on subsequent request
    # storing all data in resources folders
    storage = JSONStorage("resources/products.json")
    notification = ConsoleNotification()
    scraper = Scraper(storage, notification, cache)

    result = await scraper.scrape(scraping_input.page_limit, scraping_input.proxy)
    return {"message": "Scraping completed", "products_scraped": result}
