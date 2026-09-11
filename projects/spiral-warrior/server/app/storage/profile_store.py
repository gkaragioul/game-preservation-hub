from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
from pathlib import Path
from threading import RLock
from typing import Iterator

from app.models.save import LocalProfile


DEFAULT_SAVE_DIR = Path(__file__).resolve().parents[1] / "saves" / "runtime"
_profile_transaction_lock = RLock()


@contextmanager
def profile_transaction() -> Iterator[None]:
    with _profile_transaction_lock:
        yield


def runtime_save_dir() -> Path:
    return Path(os.environ.get("SPIRAL_SAVE_DIR", DEFAULT_SAVE_DIR))


class ProfileStore:
    def __init__(self, root: Path | None = None):
        self.root = root or runtime_save_dir()

    def _path(self, account: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", account)[:64] or "local"
        return self.root / f"{safe}.json"

    def load(self, account: str = "local") -> LocalProfile:
        with profile_transaction():
            path = self._path(account)
            if path.exists():
                return LocalProfile.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            profile = LocalProfile(account_id=account)
            self.save(profile)
            return profile

    def save(self, profile: LocalProfile) -> None:
        with profile_transaction():
            self.root.mkdir(parents=True, exist_ok=True)
            target = self._path(profile.account_id)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(
                json.dumps(
                    profile.model_dump(), ensure_ascii=False, indent=2
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, target)
