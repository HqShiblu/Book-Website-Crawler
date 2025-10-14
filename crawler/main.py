import asyncio, json, hashlib, httpx
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bs4 import BeautifulSoup
from utils.settings import settings
from models.book import Book
from models.constant import words


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
        except Exception as e:
            print(f"Attempt {attempt} failed for {url}: {e}")
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
    availability = soup.select_one("p.availability")
    availability = availability.get_text(strip=True) if availability else None
    num_reviews = 0
    upc = ""
    rating = None
    rating_el = soup.select_one("p.star-rating")
    if rating_el:
        classes = rating_el.get("class", [])
        for c in classes:
            if c in words:
                rating = words[c]
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
        "availability": availability,
        "num_reviews": num_reviews,
        "rating": rating,
        "image_url": image_url,
        "source_url": source_url,
    }
    return data

async def crawl_books():
    
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    books = db["books"]
    books.create_index("source_url", unique=True)

    async with httpx.AsyncClient() as client:
        page = 1
        found = 0
        while True:
            url = f"{BASE}/catalogue/page-{page}.html"
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
                    "availability": parsed.get("availability"),
                })
                print("Saving Data for:\n"+parsed.get("title")+", URL: "+parsed.get("source_url"))
                existing = await books.find_one({"upc": parsed.get("upc")})
                if not existing:
                    res = await books.insert_one(parsed)
                    await db.changes.insert_one({
                        "type": "new",
                        "source_url": detail_url,
                        "book_id": str(res.inserted_id),
                        "updated_at": datetime.now(),
                        "data": parsed
                    })
                    found += 1
                else:
                    if existing.get("content_hash") != parsed.get("content_hash"):
                        await books.update_one({"_id": existing["_id"]}, {"$set": parsed})
                        await db.changes.insert_one({
                            "type": "updated",
                            "source_url": detail_url,
                            "book_id": str(existing["_id"]),
                            "updated_at": datetime.now(),
                            "old_hash": existing.get("content_hash"),
                            "new_hash": parsed["content_hash"],
                            "data": parsed
                        })
                        found += 1
            page += 1

if __name__ == "__main__":
    import asyncio
    print("Crawling...")
    asyncio.run(crawl_books())

