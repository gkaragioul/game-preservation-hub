"""The committed event table must match the shipped resource."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.protocol.roguelike_events import (
    LV1_BATTLE_EVENT,
    PROLOGUE_CHAPTER_ID,
    PROLOGUE_EVENT_TYPES,
    PROLOGUE_FIXED_EXPORTS,
    PROLOGUE_RANDOM_EXPORTS,
    event_type,
    fixed_exports,
    is_battle_event,
    random_export_count,
)

ROOT = Path(__file__).resolve().parents[2]


def _extractor():
    spec = importlib.util.spec_from_file_location(
        "extract_roguelike_events", ROOT / "tools" / "extract_roguelike_events.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_battle_events_are_recognised_by_type_not_by_id():
    # Both prologue battle nodes carry the same type under different ids;
    # keying on the id alone is what stranded a run after the first battle.
    assert is_battle_event(110001)
    assert is_battle_event(110017)
    assert event_type(110001) == event_type(110017) == LV1_BATTLE_EVENT


def test_unknown_event_ids_are_not_battles():
    assert not is_battle_event(999999)
    assert not is_battle_event(110018)  # FinalBossEvent is modelled separately


@pytest.mark.preservation_artifact
def test_committed_table_matches_the_shipped_resource():
    extractor = _extractor()
    recovered = extractor.event_types(extractor.RESOURCES, PROLOGUE_CHAPTER_ID)

    assert recovered == PROLOGUE_EVENT_TYPES


def test_the_boss_rolls_more_exports_than_a_battle():
    """RandomTime is per event, and the boss's is not a battle's.

    The client rolls this many exports locally and sends them on EnterNode;
    demanding a battle's three refuses the boss outright.
    """
    assert random_export_count(110001) == 3
    assert random_export_count(110017) == 3
    assert random_export_count(110018) == 4


def test_events_with_a_fixed_export_list_roll_nothing():
    # A Select node's three choices are declared in the table, so the client
    # has nothing to roll and sends no exports.
    assert random_export_count(110002) == 0
    assert random_export_count(110005) == 0
    assert random_export_count(999999) == 0


@pytest.mark.preservation_artifact
def test_committed_export_counts_match_the_shipped_resource():
    extractor = _extractor()
    recovered = extractor.random_export_counts(
        extractor.RESOURCES, PROLOGUE_CHAPTER_ID
    )

    assert recovered == PROLOGUE_RANDOM_EXPORTS


def test_events_with_a_declared_list_expose_it():
    """A fixed list is never sent, so the gateway looks it up.

    The client leaves Event.LocationExports empty for these, which is what
    made the starter-chip branch refuse every real request.
    """
    assert fixed_exports(110019) == (100095, 100080, 100090)
    assert fixed_exports(110002) == (100018, 100019, 100020)
    assert fixed_exports(110001) == ()
    assert fixed_exports(999999) == ()


@pytest.mark.preservation_artifact
def test_committed_fixed_exports_match_the_shipped_resource():
    extractor = _extractor()
    recovered = extractor.fixed_exports(
        extractor.RESOURCES, PROLOGUE_CHAPTER_ID
    )

    assert recovered == PROLOGUE_FIXED_EXPORTS
