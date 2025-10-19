from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from utils.settings import settings
from utils.auth import check_api_key
from models.book import Book
from models.params import QueryParams
from models.constants import Switch_Map

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URI
)
rate_limit = f"{settings.LIMITER_FREQUENCY}/{settings.LIMITER_TIMING}"

app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
db = mongo_client[settings.MONGO_DB]


@app.get("/books")
@limiter.limit(rate_limit)
async def get_books(
    request: Request,
    params: QueryParams = Depends(),
    authorized: bool = Depends(check_api_key)):
    
    final_query = {}
    if params.category:
        final_query["category"] = {"$regex": params.category, "$options": "i"}
    if params.min_price is not None or params.max_price is not None:
        final_query["price_incl"] = {}
        if params.min_price is not None:
            final_query["price_incl"]["$gte"] = params.min_price
        if params.max_price is not None:
            final_query["price_incl"]["$lte"] = params.max_price
    if params.rating is not None:
        final_query["rating"] = params.rating
        
    sort = []
    sort_by_ = []
    if params.sort_by:
        sort_by_ = params.sort_by.split("|")
        sort_direction = 1
        
        if len(sort_by_)>1 and sort_by_[1]=="desc":
            sort_direction = -1
        
        if sort_by_[0] == "rating":
            sort = [("rating", sort_direction)]
        elif sort_by_[0] == "price":
            sort = [("price_incl", sort_direction)]
        elif sort_by_[0] == "reviews":
            sort = [("num_reviews", sort_direction)]
        
    skip = (params.page - 1) * params.page_size
    projection = {"raw_html": 0, "crawled_at": 0, "content_hash": 0}
    
    cursor = db.books.find(final_query, projection=projection).skip(skip).limit(params.page_size)
    
    if len(sort)!=0:
        cursor = cursor.sort(sort)
        
    books = await cursor.to_list(length=params.page_size)
    
    for book in books:
        book["_id"] = str(book["_id"])
    
    total_count = await db.books.count_documents(final_query)
    
    return {"total_count": total_count, "page": params.page, "books": books}



@app.get("/books/{book_id}")
@limiter.limit(rate_limit)
async def get_single_book(
    request: Request,
    params: QueryParams = Depends(),
    authorized: bool = Depends(check_api_key)):
    
    if not ObjectId.is_valid(params.book_id):
        raise HTTPException(status_code=400, detail="invalid id")
    
    projection = {"raw_html": 0, "crawled_at": 0, "content_hash": 0}
    
    book = await db.books.find_one({"_id": ObjectId(params.book_id)}, projection=projection)
    
    if not book:
        raise HTTPException(status_code=404, detail="not found")

    book["_id"] = str(book["_id"])
    
    return book


@app.get("/changes")
@limiter.limit(rate_limit)
async def get_changes(
    request: Request,
    params: QueryParams = Depends(),
    authorized: bool = Depends(check_api_key)):
    
    skip = (params.page - 1) * params.page_size
    
    cursor = db.changes.find({}, projection={"_id":0, "data": 0}).sort("updated_at", -1).skip(skip).limit(params.page_size)
        
    changes = await cursor.to_list(length=params.page_size)
    
    for change in changes:
        change["book_id"] = str(change["book_id"])
    
    total_count = await db.changes.count_documents({})
    
    return {"total_count": total_count, "page": params.page, "changes": changes}
