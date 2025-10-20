from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.openapi.models import APIKey
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from utils.settings import settings
from utils.auth import check_api_key
from models.params import QueryParams
from models.constants import Change_Status


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URI
)
rate_limit = f"{settings.LIMITER_FREQUENCY}/{settings.LIMITER_TIMING}"

app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

API_KEY_NAME = settings.API_KEY_NAME
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
db = mongo_client[settings.MONGO_DB]


@app.get("/books")
@limiter.limit(rate_limit)
async def get_books(
    request: Request,
    params: QueryParams = Depends(),
    authorized: bool = Security(check_api_key)):
    
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
    else:
        cursor = cursor.sort("crawled_at", -1)
        
    books = await cursor.to_list(length=params.page_size)
    
    for book in books:
        book["_id"] = str(book["_id"])
    
    total_count = await db.books.count_documents(final_query)
    
    return {"total_count": total_count, "page": params.page, "books": books}



@app.get("/books/{book_id}")
@limiter.limit(rate_limit)
async def get_single_book(
    request: Request,
    book_id: str,
    authorized: bool = Security(check_api_key)):
    
    if not ObjectId.is_valid(book_id):
        raise HTTPException(status_code=400, detail="invalid id")
    
    projection = {"raw_html": 0, "crawled_at": 0, "content_hash": 0}
    
    book = await db.books.find_one({"_id": ObjectId(book_id)}, projection=projection)
    
    if not book:
        raise HTTPException(status_code=404, detail="not found")

    book["_id"] = str(book["_id"])
    
    return book


@app.get("/changes")
@limiter.limit(rate_limit)
async def get_changes(
    request: Request,
    page:int=1,
    page_size:int=20,
    authorized: bool = Security(check_api_key)):
    
    skip = (page - 1) * page_size
    
    cursor = db.changes.find({}, projection={"_id":0, "data": 0}).sort("updated_at", -1).skip(skip).limit(page_size)
        
    changes = await cursor.to_list(length=page_size)
    
    for change in changes:
        change["book_id"] = str(change["book_id"])
        change["type"] = str(Change_Status[change["type"]])
    
    total_count = await db.changes.count_documents({})
    
    return {"total_count": total_count, "page": page, "changes": changes}

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Book Crawler API",
        version="1.0.0",
        description="Book Crawler API with rate limiting and API key auth",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": API_KEY_NAME,
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

