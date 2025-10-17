import asyncio
from utils.common_crawler import crawl_books
from models.constants import CrawlerType


if __name__ == "__main__":
    asyncio.run(crawl_books(CrawlerType.Regular))
