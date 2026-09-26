"""Guard that the suite never writes into the repository save directory.

The WebSocket gateway journals every frame beneath ``runtime_save_dir()``. When
a test connects without redirecting that directory, the journal and profile of
the operator's real local account are rewritten by the suite.
"""

from __future__ import annotations

from app.storage.profile_store import DEFAULT_SAVE_DIR, runtime_save_dir


def test_suite_runs_against_an_isolated_save_directory():
    assert runtime_save_dir() != DEFAULT_SAVE_DIR
    assert DEFAULT_SAVE_DIR not in runtime_save_dir().parents
