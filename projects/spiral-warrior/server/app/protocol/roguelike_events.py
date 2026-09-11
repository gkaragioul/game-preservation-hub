"""Event type table for the RogueLike prologue chapter.

A node's event type is never sent by the client. `setEvent` reads
`eventData.EventType`, a lookup into the shipped `data/RogueLike` binary
table, so the gateway needs the same mapping to tell a battle node from a
shop, a reward or the boss.

The table below is generated from the immutable extraction by
``tools/extract_roguelike_events.py``. It is committed rather than parsed at
runtime because the resource is an untracked preservation input: a clean
checkout has to run without it.
``server/tests/test_roguelike_events.py`` regenerates it from the artifact
when one is present, so drift is caught rather than assumed away.
"""

from __future__ import annotations

# ERogueLikeType, from the decrypted bundle.
INVALID_EVENT = 0
LV1_BATTLE_EVENT = 1
LV2_BATTLE_EVENT = 2
LV3_BATTLE_EVENT = 3
LV4_BATTLE_EVENT = 4
FINAL_BOSS_EVENT = 5
TALK_EVENT = 6
SELECT_EVENT = 7
REWARD_EVENT = 8
SHOPPING_EVENT = 9
NORMAL_CHIJI_ITEM_EVENT = 10
RARE_CHIJI_ITEM_EVENT = 11
START_EVENT = 12
FINISH_EVENT = 13
AFTER_BOSS_TALK_EVENT = 16

BATTLE_EVENT_TYPES = frozenset(
    {
        LV1_BATTLE_EVENT,
        LV2_BATTLE_EVENT,
        LV3_BATTLE_EVENT,
        LV4_BATTLE_EVENT,
    }
)

# doTrigger routes the boss through the same branch as a battle, so it is
# entered and fought identically. The branch then guards the postbattle
# chooser with `eventType !== FinalBossEvent`, so a boss win is final and no
# chip claim ever follows it.
FIGHTABLE_EVENT_TYPES = BATTLE_EVENT_TYPES | {FINAL_BOSS_EVENT}

PROLOGUE_CHAPTER_ID = -1

# data/RogueLike, BelongChapter == -1. Twenty events make up chapter 00.
PROLOGUE_EVENT_TYPES: dict[int, int] = {
    110000: START_EVENT,
    110001: LV1_BATTLE_EVENT,
    110002: SELECT_EVENT,
    110003: REWARD_EVENT,
    110005: TALK_EVENT,
    110010: TALK_EVENT,
    110011: TALK_EVENT,
    110012: TALK_EVENT,
    110013: TALK_EVENT,
    110014: TALK_EVENT,
    110015: TALK_EVENT,
    110016: TALK_EVENT,
    110017: LV1_BATTLE_EVENT,
    110018: FINAL_BOSS_EVENT,
    110019: NORMAL_CHIJI_ITEM_EVENT,
    110020: AFTER_BOSS_TALK_EVENT,
    110021: AFTER_BOSS_TALK_EVENT,
    110022: AFTER_BOSS_TALK_EVENT,
    110023: AFTER_BOSS_TALK_EVENT,
    110024: AFTER_BOSS_TALK_EVENT,
}


# data/RogueLike RandomTime, for the events that declare one. The client
# rolls this many exports locally in `makeRandomExport` and sends them on
# EnterNode, because the gateway cannot reproduce the roll. Events with a
# fixed `ExportIdArray` roll nothing and are absent here. The count is per
# event, not per kind: the boss draws four where a battle draws three, and
# demanding a battle's three refuses the boss outright.
PROLOGUE_RANDOM_EXPORTS: dict[int, int] = {
    110001: 3,
    110003: 3,
    110017: 3,
    110018: 4,
}


# data/RogueLike ExportIdArray. A declared list is neither rolled nor sent:
# `setEvent` assigns it locally and `getRogueLikeNode` leaves the request's
# `Event.LocationExports` empty, so the gateway has to look it up here.
# Expecting the client to echo it back is what refused the starter-chip
# branch and stranded a run on the story node.
PROLOGUE_FIXED_EXPORTS: dict[int, tuple[int, ...]] = {
    110002: (100018, 100019, 100020),
    110016: (100007,),
    110019: (100095, 100080, 100090),
}


def event_type(event_id: int) -> int:
    """Return the declared event type, or INVALID_EVENT when unknown."""
    return PROLOGUE_EVENT_TYPES.get(event_id, INVALID_EVENT)


def random_export_count(event_id: int) -> int:
    """How many exports the client rolls for this event, zero if none."""
    return PROLOGUE_RANDOM_EXPORTS.get(event_id, 0)


def fixed_exports(event_id: int) -> tuple[int, ...]:
    """The exports this event declares, empty when it declares none."""
    return PROLOGUE_FIXED_EXPORTS.get(event_id, ())


def is_battle_event(event_id: int) -> bool:
    """A normal battle: fought, then offers a postbattle chip."""
    return event_type(event_id) in BATTLE_EVENT_TYPES


def is_boss_event(event_id: int) -> bool:
    """The chapter boss: fought like a battle, but the win is final."""
    return event_type(event_id) == FINAL_BOSS_EVENT


def is_fightable_event(event_id: int) -> bool:
    return event_type(event_id) in FIGHTABLE_EVENT_TYPES


def is_declared_event(event_id: int) -> bool:
    """Whether the chapter declares this event at all."""
    return event_id in PROLOGUE_EVENT_TYPES
