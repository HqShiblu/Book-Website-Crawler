from functools import lru_cache
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB: str
    CRAWL_URL: str
    SCHEDULER_HOUR:int
    SCHEDULER_MINUTE:int
    GENERATE_CHANGE_REPORT:bool
    REDIS_URI:str
    API_KEY:str
    LIMITER_FREQUENCY:str
    LIMITER_TIMING:str
        
    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

