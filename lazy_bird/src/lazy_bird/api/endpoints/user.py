from fastapi import APIRouter, Response

import lazy_bird.crud.user as UserCrud
from lazy_bird.schemas.user import UserIn, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
def get_all_users():
    return UserCrud.get_all()


@router.post("/", response_model=UserOut, status_code=201)
def create_user(payload: UserIn):
    return UserCrud.create(payload)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    return UserCrud.get(user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate):
    return UserCrud.update(user_id, payload.model_dump(exclude_unset=True))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int):
    UserCrud.delete(user_id)
    return Response(status_code=204)
