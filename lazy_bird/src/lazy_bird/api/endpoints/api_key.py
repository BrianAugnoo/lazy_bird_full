from fastapi import APIRouter, Response

import lazy_bird.crud.api_key as APIKey
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.api_key import APIKeyIn, APIKeyOut, APIKeyUpdate

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("/", response_model=APIKeyOut, status_code=201)
def create_api_key(api_key_in: APIKeyIn):
    created = APIKey.create(api_key_in)
    APIKey.on_change(api_key_in.name)
    return created


@router.get("/", response_model=list[APIKeyOut])
def list_api_keys():
    """Stored API keys (names only: secrets are never returned)."""
    return APIKey.get_all()


@router.get("/{name}", response_model=APIKeyOut)
def get_api_key(name: str):
    api_key = APIKey.find(name)
    if api_key is None:
        raise NotFoundError("API key", name)
    return api_key


@router.put("/{name}", response_model=APIKeyOut)
def replace_api_key(name: str, payload: APIKeyUpdate):
    """Replace the secret of a stored key."""
    updated = APIKey.update(name, payload.key)
    APIKey.on_change(name)
    return updated


@router.delete("/{name}", status_code=204)
def delete_api_key(name: str):
    APIKey.delete(name)
    APIKey.on_change(name, removed=True)
    return Response(status_code=204)
