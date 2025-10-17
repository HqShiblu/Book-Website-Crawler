import asyncio
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from utils.common_crawler import crawl_books
from models.constants import CrawlerType
from util.settings import settings

scheduler = BlockingScheduler()

scheduler.add_job(crawl_books, 'cron', args=[CrawlerType.Scheduler], hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE)

scheduler.start()

