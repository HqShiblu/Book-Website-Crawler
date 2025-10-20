from fastapi import HTTPException, Request
from utils.settings import settings

def check_api_key(request: Request):
    api_key = request.headers.get(settings.API_KEY_NAME)
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

