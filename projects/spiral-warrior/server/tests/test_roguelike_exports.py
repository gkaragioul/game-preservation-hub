"""The committed Select export table must match the shipped resource."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.protocol.roguelike_exports import (
    CHIJI_ITEM_REWARD,
    PROLOGUE_CHAPTER_ID,
    ITEM_REWARD,
    PROLOGUE_REWARD_EXPORTS,
    PROLOGUE_SELECT_EXPORTS,
    RECOVER_HP_REWARD,
    REWARD_EVENT_TYPE,
    SELECT_EVENT_TYPE,
    reward_export,
    select_export,
)

ROOT = Path(__file__).resolve().parents[2]


def _extractor():
    spec = importlib.util.spec_from_file_location(
        "extract_roguelike_exports",
        ROOT / "tools" / "extract_roguelike_exports.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_repair_export_carries_the_shipped_percentage():
    # The repair station restores 40% - the confirm dialog then halves it for
    # a defeated top. Both numbers come from this one row, not from us.
    export = select_export(1)
    assert export is not None
    assert export.reward_type == RECOVER_HP_REWARD
    assert export.export_num == 40
    assert export.export_key == 100020


def test_chip_exports_are_distinguished_by_their_item_id():
    # The confirm sends only NowToyTops[chosen].Buffs = [ExportItemId], so
    # the item id has to identify the choice on its own.
    attack = select_export(4301)
    structure = select_export(4302)
    assert attack is not None and structure is not None
    assert attack.reward_type == structure.reward_type == CHIJI_ITEM_REWARD
    assert attack.export_key != structure.export_key
    assert len(PROLOGUE_SELECT_EXPORTS) == 3


def test_unknown_item_ids_resolve_to_nothing():
    assert select_export(0) is None
    assert select_export(4231) is None  # a postbattle chip, not a Select one


@pytest.mark.preservation_artifact
def test_committed_table_matches_the_shipped_resource():
    extractor = _extractor()
    recovered = extractor.exports(
        extractor.RESOURCES, PROLOGUE_CHAPTER_ID, SELECT_EVENT_TYPE
    )

    assert recovered == {
        item_id: (export.export_key, export.reward_type, export.export_num)
        for item_id, export in PROLOGUE_SELECT_EXPORTS.items()
    }


def test_reward_exports_are_looked_up_by_export_key():
    """A reward chest confirms with the export keys it was entered with.

    A Select confirm names its pick by item id; a reward node sends the keys
    back untouched, so the two tables need different indexes.
    """
    gold = reward_export(100023)
    assert gold is not None
    assert gold.reward_type == ITEM_REWARD
    assert (gold.export_item_id, gold.export_num) == (1227894833, 500)
    assert set(PROLOGUE_REWARD_EXPORTS) == {100021, 100022, 100023}
    assert reward_export(100018) is None  # a Select row, not a reward one


@pytest.mark.preservation_artifact
def test_committed_reward_table_matches_the_shipped_resource():
    extractor = _extractor()
    recovered = extractor.exports_by_key(
        extractor.RESOURCES, PROLOGUE_CHAPTER_ID, REWARD_EVENT_TYPE
    )

    assert recovered == {
        key: (export.export_item_id, export.reward_type, export.export_num)
        for key, export in PROLOGUE_REWARD_EXPORTS.items()
    }
