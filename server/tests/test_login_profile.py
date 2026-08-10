from fastapi.testclient import TestClient
from app.main import app

def test_login_stub():
    client = TestClient(app)
    r = client.get('/login/1/?account=local_player')
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    assert data['language'] == 'zh'
    assert data['servers'][0]['server_name'] == '本地离线服'

def test_profile_stub(monkeypatch, tmp_path):
    monkeypatch.setenv('SPIRAL_SAVE_DIR', str(tmp_path))
    client = TestClient(app)
    r = client.get('/profile')
    assert r.status_code == 200
    data = r.json()
    assert data['profile']['account_id'] == 'local'
    assert data['profile']['player_id'] == 100000001
    assert data['profile']['language'] == 'zh'
