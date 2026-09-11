import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True


@pytest.mark.parametrize(
    "method",
    [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
        "TRACE",
        "CONNECT",
    ],
)
def test_unknown_http_method_returns_404(method: str):
    response = TestClient(app).request(method, "/missing")
    assert response.status_code == 404
    if method != "HEAD":
        assert response.json()["ok"] is False
