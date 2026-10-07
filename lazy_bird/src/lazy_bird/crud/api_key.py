from lazy_bird.database import db
from lazy_bird.models.api_key import APIKey as APIKeyORM
from lazy_bird.schemas.api_key import APIKeyOut, APIKeyIn
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from .error import UniqueFieldError


def create(api_key_in: APIKeyIn):
    with db() as session:
        api_key = APIKeyORM.model_validate(api_key_in)
        session.add(api_key)
        try:
            session.commit()
            session.refresh(api_key)
            return APIKeyOut.model_validate(api_key)
        except IntegrityError:
            session.rollback()
            raise UniqueFieldError(field_name="name", field_value=api_key_in.name)

def find(name: str):
    with db() as session:
        api_key = session.get(APIKeyORM, name)
        if api_key is None:
            return None
        return APIKeyOut.model_validate(api_key)

def find_key(name: str) -> str | None:
    with db() as session:
        api_key = session.get(APIKeyORM, name)
        return api_key.key if api_key else None

def get_all():
    with db() as session:
        statement = select(APIKeyORM)
        api_keys = session.exec(statement).all()
        return [APIKeyOut.model_validate(api_key) for api_key in api_keys]


HUGGING_FACE_KEY = "HuggingFace"


def update(name: str, key: str) -> APIKeyOut:
    from lazy_bird.errors import NotFoundError

    with db() as session:
        api_key = session.get(APIKeyORM, name)
        if api_key is None:
            raise NotFoundError("API key", name)
        api_key.key = key
        session.add(api_key)
        session.commit()
        return APIKeyOut.model_validate(api_key)


def delete(name: str) -> None:
    from lazy_bird.errors import NotFoundError

    with db() as session:
        api_key = session.get(APIKeyORM, name)
        if api_key is None:
            raise NotFoundError("API key", name)
        session.delete(api_key)
        session.commit()


def on_change(name: str) -> None:
    """Log in to Hugging Face again when its key changes."""
    if name == HUGGING_FACE_KEY:
        from lazy_bird.tools.hf_auth import authenticate_hf

        authenticate_hf()
