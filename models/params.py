from typing import Optional
from pydantic import BaseModel, Field

class QueryParams(BaseModel):
    book_id:Optional[str] = None
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rating: Optional[int] = None
    sort_by: Optional[str] = Field(
        None,
        pattern="^(rating|price|reviews)$",
        description="Sort by rating, price or reviews"
    )
    page: int = 1
    page_size: int = 20
