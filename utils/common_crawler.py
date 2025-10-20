import re, json, hashlib, httpx
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from .settings import settings
from models.constants import CrawlerType, Words
from models.book import Book
from utils.logger import get_logger


BASE = settings.CRAWL_URL


async def fetch_text(client: httpx.AsyncClient, url: str, timeout=20, retries=3, logger=None) -> str:
    last_status = 0
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text, last_status
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code
            log_message = f"Attempt {attempt} failed for {url}: {e}"
            print(log_message)
            logger.error(log_message)
        except Exception as e:
            log_message = f"Attempt {attempt} failed for {url}: {e}"
            print(log_message)
            logger.error(log_message)
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

def get_file_name(today, page_no):
    report_file = f"Change-Log-{today.strftime("%Y.%m.%d")}-{page_no}.json"
    report_file = Path(f"change_reports/{report_file}").resolve()    
    report_file.parent.mkdir(parents=True, exist_ok=True)
    return report_file
    

async def crawl_books(crawler_type:CrawlerType):
    
    log_name = "crawler"
    
    if crawler_type!=CrawlerType.Regular:
        log_name = "scheduler"
    
    log_name = log_name+"-"+datetime.now().strftime("%Y.%m.%d")+".log"
    
    logger = get_logger(__name__, log_name)
    
    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB]
    books = db["books"]
    books.create_index("upc", unique=True)
    books.create_index("source_url", unique=True)
    
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    async with httpx.AsyncClient() as client:
        page_no = 1
        page_log = None
        if crawler_type==CrawlerType.Regular:
            page_log = await db.page_log.find_one({})
        if page_log:
            page_no = int(page_log.get("page_no"))
        else:
            if crawler_type==CrawlerType.Regular:
                await db.page_log.insert_one({"page_no":page_no})
        
        log_message = f"Started Crawling from {crawler_type.value} at {datetime.now()}"
        print(log_message)
        logger.info(log_message)
        
        while True:
            try:
                if crawler_type==CrawlerType.Regular:
                    await db.page_log.update_one(
                        {"page_no": {"$ne": page_no}},
                        {"$set": {"page_no": page_no}}
                    )
                url = f"{BASE}/catalogue/page-{page_no}.html"
                
                html, http_status = await fetch_text(client, url, logger=logger)
                if int(http_status)==404:
                    break
                soup = BeautifulSoup(html, "lxml")
                items = soup.select("article.product_pod h3 a")
                if not items:
                    break
                for a in items:
                    href = a.get("href")
                    detail_url = BASE +"/catalogue/"+ href
                    existing = await books.find_one({"source_url": detail_url})
                    if crawler_type==CrawlerType.Regular and existing:
                        continue
                    detail_html, http_status = await fetch_text(client, detail_url, logger=logger)
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
                    if not existing:
                        log_message = "Added New Book:\n"+parsed.get("title")+", URL: "+parsed.get("source_url")
                        print(log_message)
                        logger.info(log_message)
                        async with await mongo_client.start_session() as session:
                            async with session.start_transaction():
                                new_book = await books.insert_one(parsed)
                                if crawler_type==CrawlerType.Scheduler:
                                    await db.changes.insert_one({
                                        "type": 1,
                                        "book_id": new_book.inserted_id,
                                        "source_url": detail_url,
                                        "updated_at": datetime.now(),
                                    })
                    else:
                        existing_book = Book(**existing)
                        if existing_book.content_hash != parsed.get("content_hash"):
                            changes = {}
                            change_description = []
                            if existing_book.price_incl!=parsed.get("price_incl"):
                                change_description.append("Price (including tax)")
                                changes.update({
                                    "previous_price_incl":existing_book.price_incl,
                                    "current_price_incl":parsed.get("price_incl"),
                                })
                            if existing_book.price_excl!=parsed.get("price_excl"):
                                change_description.append("Price (excluding tax)")
                                changes.update({
                                    "previous_price_excl":existing_book.price_excl,
                                    "current_price_excl":parsed.get("price_excl"),
                                })
                            if existing_book.stock!=parsed.get("stock"):
                                change_description.append("Stock")
                                changes.update({
                                    "previous_stock":existing_book.stock,
                                    "current_stock":parsed.get("stock"),
                                })
                            if existing_book.num_reviews!=parsed.get("num_reviews"):
                                change_description.append("Number of Reviews")
                                changes.update({
                                    "previous_num_reviews":existing_book.num_reviews,
                                    "current_num_reviews":parsed.get("num_reviews"),
                                })
                            if existing_book.rating!=parsed.get("rating"):
                                change_description.append("Rating")
                                changes.update({
                                    "previous_rating":existing_book.rating,
                                    "current_rating":parsed.get("rating"),
                                })
                            
                            change_description = ", ".join(change_description)+ " changed"
                            
                            async with await mongo_client.start_session() as session:
                                async with session.start_transaction():
                                    result = await books.update_one({"_id": ObjectId(existing_book.id)}, {"$set": parsed})
                                    print("Match Count")
                                    print(result.matched_count)
                                    if result.matched_count>0:
                                        await db.changes.insert_one({
                                            "type": 2,
                                            "book_id": existing_book.id,
                                            "source_url": detail_url,
                                            "updated_at": datetime.now(),
                                            "change_description":change_description,
                                            "changes":changes,
                                        })
                            
                            log_message = "Updated Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url")
                            print(log_message)
                            print(change_description)
                            logger.info(log_message)
                            logger.info(change_description)
                page_no += 1
            except Exception as e:
                log_message = f"Error on crawling: {e}"
                print(log_message)
                logger.error(log_message)
        
    log_message = f"Completed Crawling from {crawler_type.value} at {datetime.now()}"
    print(log_message)
    logger.info(log_message)
    
    if crawler_type==CrawlerType.Scheduler and settings.GENERATE_CHANGE_REPORT:
        log_message = f"Generating Daily Change Report for {today.strftime("%d-%m-%Y")}"
        print(log_message)
        logger.info(log_message)
        
        batch_size = 500
        page_count = 1
        last_id = None
        
        while True:
            query = {
                "updated_at": {"$gte": today, "$lt": tomorrow}
            }
            
            if last_id:
                query["_id"] = {"$gt": ObjectId(last_id)}
            
            cursor = db.changes.find(query).sort("_id", 1).limit(batch_size)
            docs = await cursor.to_list(length=batch_size)
                        
            if not docs:
                break
            
            report_file = get_file_name(today, page_count)
                        
            with open(report_file, "a", encoding="utf-8") as f:
                for doc in docs:
                    doc["_id"] = str(doc["_id"])
                    doc["book_id"] = str(doc["book_id"])
                    if "updated_at" in doc:
                        doc["updated_at"] = doc["updated_at"].isoformat()
                f.write(json.dumps(docs))
            
            last_id = str(docs[-1]["_id"])
            page_count += 1
        
        
        log_message = f"Daily Change Report Generation for {today.strftime("%d-%m-%Y")} Complete"
        print(log_message)
        logger.info(log_message)
        
        