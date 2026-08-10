#!/usr/bin/env python3
"""Recover the RogueLike event table from the shipped Cocos resources.

A node's event type is never sent by the client: `setEvent` reads
`eventData.EventType`, a lookup into the `data/RogueLike` binary table. The
gateway needs the same mapping to tell a battle node from a shop or the boss,
so this recovers it from the immutable extraction and prints it as the table
committed in ``server/app/protocol/roguelike_events.py``.

Usage:

    python tools/extract_roguelike_events.py                 # prologue only
    python tools/extract_roguelike_events.py --chapter all   # every chapter
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cocos_tables import RESOURCES, read_records, resolve_table, signed

TABLE_PATH = "data/RogueLike"

# Field numbers from the generated encoder in the decrypted bundle.
FIELD_EVENT_ID = 1
FIELD_BELONG_CHAPTER = 3
FIELD_EVENT_TYPE = 5
FIELD_RANDOM_TIME = 14
FIELD_EXPORT_ID_ARRAY = 11

PROLOGUE_CHAPTER = -1

EVENT_TYPE_NAMES = {
    0: "InvalidEvent",
    1: "Lv1BattleEvent",
    2: "Lv2BattleEvent",
    3: "Lv3BattleEvent",
    4: "Lv4BattleEvent",
    5: "FinalBossEvent",
    6: "TalkEvent",
    7: "SelectEvent",
    8: "RewardEvent",
    9: "ShoppingEvent",
    10: "NormalChijiItemEvent",
    11: "RareChijiItemEvent",
    12: "StartEvent",
    13: "FinishEvent",
    14: "Lv1TalkEvent",
    15: "Lv2TalkEvent",
    16: "AfterBossTalkEvent",
    17: "TalentExpEvent",
    18: "Lv1RewardEvent",
    19: "Lv2RewardEvent",
    20: "BattlePassReward",
    21: "ShopBattleEvent",
}


def event_types(resources: Path, chapter: int | None) -> dict[int, int]:
    records = read_records(
        resolve_table(resources, TABLE_PATH), FIELD_EVENT_ID
    )
    return {
        record[FIELD_EVENT_ID]: record.get(FIELD_EVENT_TYPE, 0)
        for record in records
        if chapter is None
        or signed(record.get(FIELD_BELONG_CHAPTER, 0)) == chapter
    }


def random_export_counts(
    resources: Path, chapter: int | None
) -> dict[int, int]:
    """RandomTime per event, omitting the events that roll nothing.

    The client rolls this many exports in `makeRandomExport` and sends them
    on EnterNode; events with a fixed `ExportIdArray` roll none.
    """
    records = read_records(
        resolve_table(resources, TABLE_PATH), FIELD_EVENT_ID
    )
    return {
        record[FIELD_EVENT_ID]: record[FIELD_RANDOM_TIME]
        for record in records
        if record.get(FIELD_RANDOM_TIME, 0)
        and (
            chapter is None
            or signed(record.get(FIELD_BELONG_CHAPTER, 0)) == chapter
        )
    }


def fixed_exports(
    resources: Path, chapter: int | None
) -> dict[int, tuple[int, ...]]:
    """ExportIdArray per event, omitting the events that declare none.

    A fixed list is not rolled and not sent: the client leaves
    `Event.LocationExports` empty and the gateway looks the list up here.
    """
    records = read_records(
        resolve_table(resources, TABLE_PATH),
        FIELD_EVENT_ID,
        repeated=frozenset({FIELD_EXPORT_ID_ARRAY}),
    )
    return {
        record[FIELD_EVENT_ID]: record[FIELD_EXPORT_ID_ARRAY]
        for record in records
        if record.get(FIELD_EXPORT_ID_ARRAY)
        and (
            chapter is None
            or signed(record.get(FIELD_BELONG_CHAPTER, 0)) == chapter
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chapter",
        default=str(PROLOGUE_CHAPTER),
        help="chapter to emit, or 'all' for every chapter",
    )
    arguments = parser.parse_args()
    chapter = None if arguments.chapter == "all" else int(arguments.chapter)

    mapping = event_types(RESOURCES, chapter)
    rolls = random_export_counts(RESOURCES, chapter)
    print(f"# {len(mapping)} events, chapter {arguments.chapter}")
    for event_id, event_type in sorted(mapping.items()):
        name = EVENT_TYPE_NAMES.get(event_type, "?")
        print(f"    {event_id}: {event_type},  # {name}")
    print(f"# {len(rolls)} events roll exports, chapter {arguments.chapter}")
    for event_id, count in sorted(rolls.items()):
        print(f"    {event_id}: {count},")
    fixed = fixed_exports(RESOURCES, chapter)
    print(f"# {len(fixed)} events declare exports, chapter {arguments.chapter}")
    for event_id, exports in sorted(fixed.items()):
        print(f"    {event_id}: {exports},")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
