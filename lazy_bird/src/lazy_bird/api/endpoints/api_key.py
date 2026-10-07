from fastapi import APIRouter
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.api_key import APIKeyIn, APIKeyOut
import lazy_bird.crud.api_key as APIKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("/", response_model=APIKeyOut, status_code=201)
def create_api_key(api_key_in: APIKeyIn):
    return APIKey.create(api_key_in)


@router.get("/", response_model=list[APIKeyOut])
def list_api_keys():
    return APIKey.get_all()


@router.get("/{name}", response_model=APIKeyOut)
def get_api_key(name: str):
    api_key = APIKey.find(name)
    if api_key is None:
        raise NotFoundError("API key", name)
    return api_key
