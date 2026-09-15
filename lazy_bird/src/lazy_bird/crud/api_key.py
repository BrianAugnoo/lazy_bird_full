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

def get_all():
    with db() as session:
        statement = select(APIKeyORM)
        api_keys = session.exec(statement).all()
        return [APIKeyOut.model_validate(api_key) for api_key in api_keys]