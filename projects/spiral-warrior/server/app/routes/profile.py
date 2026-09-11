from fastapi import APIRouter
from pydantic import BaseModel

from app.storage.profile_store import ProfileStore, profile_transaction


router = APIRouter()


class ProfileUpdate(BaseModel):
    level: int
    stages_unlocked: list[int]


@router.get('/profile')
@router.get('/player/profile')
@router.get('/user/profile')
@router.get('/game/profile')
def profile():
    return ProfileStore().load("local").to_client_response()


@router.put('/profile')
def update_profile(update: ProfileUpdate):
    store = ProfileStore()
    with profile_transaction():
        profile = store.load("local")
        profile.level = update.level
        profile.stages_unlocked = update.stages_unlocked
        store.save(profile)
    return profile.to_client_response()
