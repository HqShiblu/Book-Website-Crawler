from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        return str(v)

class Book(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    upc:str
    title: str
    category: Optional[str]
    description: Optional[str]
    price_incl: Optional[float]
    price_excl: Optional[float]
    is_available: bool
    stock:int
    num_reviews: Optional[int]
    rating: Optional[int]
    image_url: Optional[HttpUrl]
    source_url: str
    raw_html: Optional[str]
    content_hash: Optional[str]
    crawled_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
