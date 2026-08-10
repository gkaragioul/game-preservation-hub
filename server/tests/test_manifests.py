from fastapi.testclient import TestClient
from app.main import app

def test_project_manifest():
    client = TestClient(app)
    r = client.get('/remote-assets/project.manifest')
    assert r.status_code == 200
    data = r.json()
    assert data['version'].endswith('local-en')
    assert 'assets' in data

def test_version_manifest_alias():
    client = TestClient(app)
    r = client.get('/oversea/remote-assets/version.manifest')
    assert r.status_code == 200
    assert r.json()['version'].endswith('local-en')
