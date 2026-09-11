"""Shared test isolation for the local gateway suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_save_dir(tmp_path, monkeypatch):
    """Redirect every test away from the operator's real save directory.

    Tests that need their own directory still call ``monkeypatch.setenv``; that
    assignment runs after this fixture and wins.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path / "saves"))
