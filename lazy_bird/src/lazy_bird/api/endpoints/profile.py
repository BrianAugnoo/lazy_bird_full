from fastapi import APIRouter

import lazy_bird.crud.profile as ProfileCrud
from lazy_bird.schemas.profile import ProfileIn, ProfileOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/", response_model=ProfileOut)
def get_profile():
    """The user the agents currently work for (the first user added, until another is chosen)."""
    return ProfileCrud.get()


@router.put("/", response_model=ProfileOut)
def switch_profile_user(payload: ProfileIn):
    """Make another user the one the agents work for."""
    return ProfileCrud.switch_to(payload.user_id)
