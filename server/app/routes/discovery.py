from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.protocol.area import AREA_RESPONSE_TEXT

router = APIRouter()


@router.api_route("/area/listV2", methods=["GET", "POST"])
def area_list_v2() -> PlainTextResponse:
    return PlainTextResponse(
        AREA_RESPONSE_TEXT,
        media_type="text/plain",
        headers={"Content-Type": "text/plain; charset=US-ASCII"},
    )
