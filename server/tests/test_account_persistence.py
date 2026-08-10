from pathlib import Path
import threading

from fastapi.testclient import TestClient

from app.main import app
from app.models.save import LocalProfile
from app.security.logic_token import verify_logic_token
from app.storage import profile_store as profile_store_module
from app.storage.profile_store import ProfileStore


def test_auth_es_issues_client_decodable_logic_token(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    response = TestClient(app).get("/auth/es?account=local")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    payload = verify_logic_token(response.text)
    assert payload == {
        "code": 1,
        "playerid": 100000001,
        "entry": "ws://10.0.2.2:23101/ws",
    }


def test_profile_write_survives_repository_restart(tmp_path: Path):
    first = ProfileStore(tmp_path)
    profile = first.load("local")
    profile.level = 2
    profile.stages_unlocked = [1, 2]
    first.save(profile)

    second = ProfileStore(tmp_path)
    restored = second.load("local")
    assert restored.player_id == 100000001
    assert restored.level == 2
    assert restored.stages_unlocked == [1, 2]
    assert not list(tmp_path.glob("*.tmp"))


def test_put_profile_is_persisted(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    client = TestClient(app)

    update = client.put("/profile", json={"level": 3, "stages_unlocked": [1, 2]})

    assert update.status_code == 200
    assert TestClient(app).get("/profile").json()["profile"]["level"] == 3


def test_concurrent_first_load_uses_one_atomic_profile_file(
    monkeypatch, tmp_path: Path
):
    first_at_replace = threading.Event()
    second_at_replace = threading.Event()
    second_attempted_load = threading.Event()
    release_first = threading.Event()
    replace_lock = threading.Lock()
    replace_calls = 0
    original_replace = profile_store_module.os.replace

    def gated_replace(source, target):
        nonlocal replace_calls
        with replace_lock:
            replace_calls += 1
            call_number = replace_calls
        if call_number == 1:
            first_at_replace.set()
            assert release_first.wait(3)
        else:
            second_at_replace.set()
        original_replace(source, target)

    monkeypatch.setattr(profile_store_module.os, "replace", gated_replace)
    results = []
    errors: list[BaseException] = []

    def load_profile(attempted: threading.Event | None = None) -> None:
        try:
            if attempted is not None:
                attempted.set()
            results.append(ProfileStore(tmp_path).load("local"))
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=load_profile)
    second = threading.Thread(
        target=load_profile,
        args=(second_attempted_load,),
    )
    try:
        first.start()
        assert first_at_replace.wait(3)
        second.start()
        assert second_attempted_load.wait(3)
        assert not second_at_replace.wait(0.2)
    finally:
        release_first.set()
        first.join(3)
        second.join(3)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(results) == 2
    assert replace_calls == 1
    assert not second_at_replace.is_set()
    saved = tmp_path / "local.json"
    assert LocalProfile.model_validate_json(
        saved.read_text(encoding="utf-8")
    ).account_id == "local"
    assert not (tmp_path / "local.json.tmp").exists()
