from typing import Any

from pydantic import BaseModel, Field


class Currency(BaseModel):
    coins: int = 999_999
    gems: int = 999_999


class RogueLikePartState(BaseModel):
    level: int = 1
    current_skin: int = 0
    location_kerns: dict[int, int] = Field(default_factory=dict)


class RogueLikeToyTopState(BaseModel):
    hp: int
    # A run starts at full health, so the map's opening hp is the ceiling.
    # Nothing else on the wire carries it, and a repair node needs it: the
    # reward is a percentage of maximum health.
    max_hp: int = 0
    buffs: dict[int, int] = Field(default_factory=dict)
    parts: dict[int, RogueLikePartState] = Field(default_factory=dict)


class RogueLikeNodeState(BaseModel):
    status: int
    event_id: int | None = None
    location_exports: list[int] = Field(default_factory=list)


class RogueLikeRunState(BaseModel):
    version: int
    chapter_id: int = -1
    chapter_level: int = 1
    random_seed: int
    map_id: int = 0
    location: int = 3
    main_top: int = 1
    emitter: int = 0
    toy_tops: dict[int, RogueLikeToyTopState]
    nodes: dict[int, RogueLikeNodeState] = Field(default_factory=dict)
    event_buffs: dict[int, int] = Field(default_factory=dict)
    battle_wins: int = 0
    pending_battle_reward: bool = False


class LocalProfile(BaseModel):
    schema_version: int = 1
    account_id: str = "local"
    player_id: int = 100000001
    nickname: str = "Local Warrior"
    language: str = "zh"
    level: int = 1
    experience: int = 0
    currency: Currency = Field(default_factory=Currency)
    tutorial_state: str = "start"
    inventory: list[dict[str, Any]] = Field(default_factory=list)
    tops: list[dict[str, Any]] = Field(default_factory=list)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    stages_unlocked: list[int] = Field(default_factory=lambda: [1])
    stages_completed: list[int] = Field(default_factory=list)
    stage_results: dict[int, int] = Field(default_factory=dict)
    roguelike_keys: int = 1
    # Day the empty key count was last refilled, YYYY-MM-DD UTC.
    roguelike_keys_refreshed_on: str = ""
    # RogueLikeRecord.LevelProcess: difficulty -> the furthest chapter id
    # beaten at it. `checkIsUnlock` compares a chapter against this, so it is
    # the whole record of what has been cleared.
    roguelike_cleared_chapters: dict[int, int] = Field(default_factory=dict)
    roguelike_enter_map_num: int = 0
    default_items: dict[int, int] = Field(default_factory=dict)
    roguelike_run: RogueLikeRunState | None = None

    def to_client_response(self) -> dict[str, Any]:
        data = self.model_dump()
        return {"ok": True, "code": 0, "profile": data, "player": data}
