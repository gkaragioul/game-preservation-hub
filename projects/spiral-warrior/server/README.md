# Spiral Warrior Local Backend

FastAPI local/offline backend emulator for the Spiral Warrior English preservation prototype.

## Setup

```bash
cd /path/to/spiral-warrior/server
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run tests

```bash
pytest -q
```

## Run server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 18080
```

## Smoke checks

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/remote-assets/project.manifest
curl 'http://127.0.0.1:18080/login/1/?account=local_player'
curl http://127.0.0.1:18080/profile
```

## Status

Schemas are provisional until verified with runtime captures from the Android client.
