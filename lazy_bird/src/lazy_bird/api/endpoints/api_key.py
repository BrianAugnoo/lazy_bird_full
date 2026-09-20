from fastapi import APIRouter, HTTPException
from lazy_bird.crud.error import UniqueFieldError
from lazy_bird.schemas.api_key import APIKeyIn, APIKeyOut
import lazy_bird.crud.api_key as APIKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

@router.post("/api-keys", response_model=APIKeyOut)
def create_api_key(api_key_in: APIKeyIn):
    try:
        return APIKey.create(api_key_in)
    except UniqueFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api-keys/{name}", response_model=APIKeyOut)
def get_api_key(name: str):
    api_key = APIKey.find(name)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key

@router.get("/api-keys", response_model=list[APIKeyOut])
def list_api_keys():
    try:
        return APIKey.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))