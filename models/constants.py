from enum import Enum


class CrawlerType(Enum):
    Regular:str = "Regular Crawler"
    Scheduler:str = "Scheduler Crawler"

Words = {
    "One":1,
    "Two":2,
    "Three":3,
    "Four":4,
    "Five":5
}

Change_Status = {
    1: "New Book Added",
    2: "Changed",
}


Switch_Map = {
    "$switch": {
        "branches": [{"case": {"$eq": ["$type", k]}, "then": v} for k, v in Change_Status.items()],
        "default": "Unknown"
    }
}
