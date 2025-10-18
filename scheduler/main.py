import asyncio
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from utils.common_crawler import crawl_books
from models.constants import CrawlerType
from utils.settings import settings

scheduler = BlockingScheduler()

def run_scheduler_crawler():
    asyncio.run(crawl_books(CrawlerType.Scheduler))


scheduler.add_job(run_scheduler_crawler, 'cron', hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE)

scheduler.start()

