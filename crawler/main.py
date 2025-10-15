import asyncio
from utils.settings import settings
from utils.crawler import crawl_books
from models.constants import CrawlerType

if __name__ == "__main__":
    import asyncio
    asyncio.run(crawl_books(CrawlerType.Regular))
