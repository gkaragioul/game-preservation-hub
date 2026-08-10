#!/usr/bin/env python3
"""Recover the RogueLike export rows that resolve a Select node.

A Select node - the repair station - offers three choices. The client rolls
them locally and never tells the gateway which three it drew: the confirm
sends an *empty* `Event.LocationExports` and identifies the pick only by
setting `NowToyTops[<chosen top>].Buffs = [ExportItemId]`.

So the gateway has to look the choice up the same way the client does, in
`data/RogueLikeExport`: the row's `RewardType` says whether it repairs the top
or grants a chip, and `ExportNum` says by how much. This prints the table
committed in ``server/app/protocol/roguelike_exports.py``.

Usage:

    python tools/extract_roguelike_exports.py                # Select rows
    python tools/extract_roguelike_exports.py --event-type 9 # shop rows
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cocos_tables import RESOURCES, read_records, resolve_table, signed

TABLE_PATH = "data/RogueLikeExport"

# Field numbers from the generated encoder in the decrypted bundle.
FIELD_EXPORT_KEY = 1
FIELD_EXPORT_ITEM_ID = 2
FIELD_REWARD_TYPE = 3
FIELD_EXPORT_NUM = 5
FIELD_BELONG_CHAPTER = 7
FIELD_EVENT_TYPE = 9

PROLOGUE_CHAPTER = -1
SELECT_EVENT = 7

REWARD_TYPE_NAMES = {
    1: "Item",
    2: "ChijiItem",
    3: "RecoverHp",
}


def exports(
    resources: Path, chapter: int, event_type: int
) -> dict[int, tuple[int, int, int]]:
    """Map ExportItemId -> (ExporotKey, RewardType, ExportNum)."""
    records = read_records(
        resolve_table(resources, TABLE_PATH), FIELD_EXPORT_KEY
    )
    selected = {}
    for record in records:
        if signed(record.get(FIELD_BELONG_CHAPTER, 0)) != chapter:
            continue
        if record.get(FIELD_EVENT_TYPE, 0) != event_type:
            continue
        item_id = record.get(FIELD_EXPORT_ITEM_ID, 0)
        selected[item_id] = (
            record[FIELD_EXPORT_KEY],
            record.get(FIELD_REWARD_TYPE, 0),
            record.get(FIELD_EXPORT_NUM, 0),
        )
    return selected


def exports_by_key(
    resources: Path, chapter: int, event_type: int
) -> dict[int, tuple[int, int, int]]:
    """Map ExporotKey -> (ExportItemId, RewardType, ExportNum).

    A reward node's confirm sends the export keys it was entered with, not
    the item ids a Select confirm carries, so it needs the other index.
    """
    records = read_records(
        resolve_table(resources, TABLE_PATH), FIELD_EXPORT_KEY
    )
    selected = {}
    for record in records:
        if signed(record.get(FIELD_BELONG_CHAPTER, 0)) != chapter:
            continue
        if record.get(FIELD_EVENT_TYPE, 0) != event_type:
            continue
        selected[record[FIELD_EXPORT_KEY]] = (
            record.get(FIELD_EXPORT_ITEM_ID, 0),
            record.get(FIELD_REWARD_TYPE, 0),
            record.get(FIELD_EXPORT_NUM, 0),
        )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", type=int, default=PROLOGUE_CHAPTER)
    parser.add_argument("--event-type", type=int, default=SELECT_EVENT)
    parser.add_argument(
        "--by-key",
        action="store_true",
        help="index by ExporotKey instead of ExportItemId",
    )
    arguments = parser.parse_args()

    if arguments.by_key:
        keyed = exports_by_key(
            RESOURCES, arguments.chapter, arguments.event_type
        )
        print(
            f"# {len(keyed)} exports, chapter {arguments.chapter}, "
            f"event type {arguments.event_type}"
        )
        for key, (item_id, reward_type, amount) in sorted(keyed.items()):
            name = REWARD_TYPE_NAMES.get(reward_type, "?")
            print(
                f"    {key}: RogueLikeExport({key}, {item_id}, "
                f"{reward_type}, {amount}),  # {name}"
            )
        return 0

    rows = exports(RESOURCES, arguments.chapter, arguments.event_type)
    print(
        f"# {len(rows)} exports, chapter {arguments.chapter}, "
        f"event type {arguments.event_type}"
    )
    for item_id, (key, reward_type, amount) in sorted(rows.items()):
        name = REWARD_TYPE_NAMES.get(reward_type, "?")
        print(
            f"    {item_id}: RogueLikeExport({key}, {item_id}, "
            f"{reward_type}, {amount}),  # {name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
