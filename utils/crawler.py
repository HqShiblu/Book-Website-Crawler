import re, json, hashlib, httpx
from datetime import datetime
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient
from .settings import settings
from models.constants import CrawlerType, Words
from models.book import Book
from utils.logger import logger


BASE = settings.CRAWL_URL

async def fetch_text(client: httpx.AsyncClient, url: str, timeout=20, retries=3) -> str:
    last_status = 0
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text, last_status
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code
            print(f"Attempt {attempt} failed for {url}: {e}")
            logger.error(f"Attempt {attempt} failed for {url}: {e}")
        except Exception as e:
            print(f"Attempt {attempt} failed for {url}: {e}")
            logger.error(f"Attempt {attempt} failed for {url}: {e}")
    return None, last_status


def compute_hash(obj: dict) -> str:
    j = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(j.encode('utf-8')).hexdigest()

def parse_book_page(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("div.product_main h1")
    title = title.get_text(strip=True) if title else ""
    desc_el = soup.select_one("#product_description ~ p")
    description = desc_el.get_text(strip=True) if desc_el else None
    category = soup.select("ul.breadcrumb li a")[-1].get_text(strip=True) if soup.select("ul.breadcrumb li a") else None
    price_incl = soup.select_one("p.price_color")
    if price_incl:
        text = price_incl.get_text(strip=True).replace('£','')
        try:
            price_incl = float(text)
        except:
            price_incl = 0
    price_excl = 0
    stock = 0
    availability = soup.select_one("p.availability")
    availability = availability.get_text(strip=True) if availability else None
    is_available = False
    if availability and "IN STOCK" in availability.upper():
        is_available = True
        match = re.search(r'\((\d+)\s+AVAILABLE\)', availability.upper())
        if match:
            stock = int(match.group(1))
    
    num_reviews = 0
    upc = ""
    rating = None
    rating_el = soup.select_one("p.star-rating")
    if rating_el:
        classes = rating_el.get("class", [])
        for c in classes:
            if c in Words:
                rating = Words[c]
    image = soup.select_one("div.carousel-inner img")
    image_url = image["src"] if image and image.get("src") else None
    if image_url and image_url.startswith("../"):
        image_url = BASE + image_url.replace("..", "")
    try:
        table = soup.select("table.table.table-striped tr")
        for tr in table:
            th = tr.select_one("th")
            td = tr.select_one("td")
            if th and td and th.get_text(strip=True).upper() == "NUMBER OF REVIEWS":
                num_reviews = int(td.get_text(strip=True))
            elif th and td and th.get_text(strip=True).upper() == "UPC":
                upc = td.get_text(strip=True)
                num_reviews = int(td.get_text(strip=True))
            elif th and td and th.get_text(strip=True).upper() == "PRICE (EXCL. TAX)":
                try:
                    price_excl = td.get_text(strip=True)
                except:
                    price_excl = 0
    except:
        num_reviews = 0

    data = {
        "upc":upc,
        "title": title,
        "description": description,
        "category": category,
        "price_incl": price_incl,
        "price_excl": price_excl,
        "is_available": is_available,
        "stock": stock,
        "num_reviews": num_reviews,
        "rating": rating,
        "image_url": image_url,
        "source_url": source_url,
    }
    return data

async def crawl_books(crawler_type:CrawlerType):
    
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    books = db["books"]
    books.create_index("upc", unique=True)

    async with httpx.AsyncClient() as client:
        page_no = 1
        page_log = None
        if crawler_type==CrawlerType.Regular:
            page_log = await db.page_log.find_one({})
        if page_log:
            page_no = int(page_log.get("page_no"))
        else:
            await db.page_log.insert_one({"page_no":page_no})
        
        print(f"Started Crawling from {crawler_type.value}")
        logger.info(f"Started Crawling from {crawler_type.value}")
        
        while True:
            try:
                await db.page_log.update_one({}, {"$set": {"page_no": page_no}})
                url = f"{BASE}/catalogue/page-{page_no}.html"
                html, http_status = await fetch_text(client, url)
                if int(http_status)==404:
                    break
                soup = BeautifulSoup(html, "lxml")
                items = soup.select("article.product_pod h3 a")
                if not items:
                    break
                for a in items:
                    href = a.get("href")
                    detail_url = BASE +"/catalogue/"+ href
                    detail_html, http_status = await fetch_text(client, detail_url)
                    if not detail_html:
                        continue
                    parsed = parse_book_page(detail_html, detail_url)
                    parsed["raw_html"] = detail_html
                    parsed["crawled_at"] = datetime.now()
                    parsed["content_hash"] = compute_hash({
                        "title": parsed.get("title"),
                        "price_incl": parsed.get("price_incl"),
                        "is_available": parsed.get("is_available"),
                        "stock": parsed.get("stock"),
                    })
                    existing = await books.find_one({"upc": parsed.get("upc")})
                    if not existing:
                        print("Saving Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url"))
                        logger.info("Saving Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url"))
                        await books.insert_one(parsed)
                    else:
                        existing_book = Book(**existing)
                        if existing_book.content_hash != parsed.get("content_hash"):
                            print("Updated Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url"))
                            logger.info("Updated Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url"))
                            await books.update_one({"_id": existing_book._id}, {"$set": parsed})
                            await db.changes.insert_one({
                                "type": "updated",
                                "source_url": detail_url,
                                "book_id": existing_book._id,
                                "updated_at": datetime.now(),
                                "old_hash": existing_book.content_hash,
                                "new_hash": parsed["content_hash"],
                                "data": parsed
                            })
                page_no += 1
            except Exception as e:
                print(f"Error on crawling: {e}")
                logger.error(f"Error on crawling: {e}")
        
        print(f"Completed Crawling from {crawler_type.value}")
        logger.info(f"Completed Crawling from {crawler_type.value}")
        
        