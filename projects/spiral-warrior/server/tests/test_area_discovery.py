import base64
from fastapi.testclient import TestClient
from app.main import app
from app.protocol.area import AREA_RESPONSE_TEXT, build_area_ret

EXPECTED_HEX = (
    "08c80112026f6b1807221e08011216687474703a2f2f31302e302e322e323a"
    "32333130312f18022002"
)
EXPECTED_TEXT = "CMgBEgJvaxgHIh4IARIWaHR0cDovLzEwLjAuMi4yOjIzMTAxLxgCIAI="


def test_area_encoder_matches_source_derived_fixture():
    assert build_area_ret().hex() == EXPECTED_HEX
    assert AREA_RESPONSE_TEXT == EXPECTED_TEXT
    assert base64.b64decode(AREA_RESPONSE_TEXT) == build_area_ret()


def test_area_route_returns_base64_text_for_get_and_post():
    client = TestClient(app)
    for method in (client.get, client.post):
        response = method("/area/listV2?clientType=7")
        assert response.status_code == 200
        assert response.text == EXPECTED_TEXT
        assert response.headers["content-type"] == "text/plain; charset=US-ASCII"
