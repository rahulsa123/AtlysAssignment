import asyncio
import os
import ssl
from urllib.parse import urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from typing import Optional
from storage import BaseStorage
from notification import BaseNotification
from cache import BaseCache
from retry import retry


class Scraper:
    # Currently using constant for url
    URL = "https://dentalstall.com/shop/page/{page_number}/"

    def __init__(self, storage: BaseStorage, notification: BaseNotification, cache: BaseCache):
        self.storage = storage
        self.notification = notification
        self.cache = cache
        self.resource_folder = "resources"
        os.makedirs(self.resource_folder, exist_ok=True)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self.ssl_context))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    @retry(exceptions=aiohttp.ClientError, tries=3, delay=5)
    async def fetch_page(self, url: str, proxy: Optional[str] = None):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, ssl=self.ssl_context) as response:
                return await response.text()

    def extract_price(self, product_details):
        price_span = product_details.find("span", class_="price")
        if price_span:
            amount_span = price_span.find("bdi")
            if amount_span:
                price_text = amount_span.get_text(strip=True)
                # Remove currency symbol and convert to float
                try:
                    return float(price_text.replace('₹', '').replace(',', ''))
                except ValueError:
                    self.notification.notify(f"Could not convert price to float: {price_text}")
        self.notification.notify(f"Price not found or invalid: {price_span}")
        return None

    async def parse_page(self, html: str):
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        shop_content = soup.find("div", class_="mf-shop-content")
        for product_details in shop_content.find_all("li"):
            if "product" in (product_details.get("class") if product_details.get("class") else ()):
                # in h2 tag product names are trimmed to support small screen rendering
                # Extracting exact product name form product image title.
                product_name = product_details.find("img").attrs.get("title").strip()
                product_price = self.extract_price(product_details)
                product_img_tag = product_details.find("img")
                products.append({"product_title": product_name, "product_price": product_price,
                                 "image_url": product_img_tag.get('data-lazy-src') or product_img_tag.get('src', '')})
        return products

    def get_image_filename(self, url: str):
        return os.path.basename(urlparse(url).path)

    async def download_image(self, url: str, path: str):
        async with self.session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(path, mode='wb') as f:
                    await f.write(await response.read())
            else:
                raise Exception(f"Failed to download image: HTTP {response.status}")

    async def process_product(self, product):
        image_filename = self.get_image_filename(product['image_url'])
        local_path = os.path.join(self.resource_folder, image_filename)
        absolute_path = os.path.abspath(local_path)
        try:
            await self.download_image(product['image_url'], local_path)
            del product['image_url']
            product['path_to_image'] = absolute_path
            self.storage.save(product)
            self.cache.set(product['product_title'], product)
            return True
        except Exception as e:
            self.notification.notify(f"Error processing product {product['product_title']}: {str(e)}")
            return False

    async def scrape(self, page_limit: Optional[int] = None, proxy: Optional[str] = None):
        async with self:  # using context manager with self to safely close all io connections using __aexit__ method
            products_scraped = 0
            page = 1

            while page_limit is None or page <= page_limit:
                html = await self.fetch_page(self.URL.format(page_number=page), proxy)
                products = await self.parse_page(html)

                tasks = []

                for product in products:
                    cached_product = self.cache.get(product['product_title'])
                    if cached_product is None or cached_product['product_price'] != product['product_price']:
                        tasks.append(self.process_product(product))

                results = await asyncio.gather(*tasks)
                products_scraped += sum(1 for result in results if result)
                if not products:
                    # if page processing failed and stopping whether request call
                    # case where page_limit > total page count on website.
                    break

                page += 1

            self.notification.notify(f"Scraped and updated {products_scraped} products")
            return products_scraped
