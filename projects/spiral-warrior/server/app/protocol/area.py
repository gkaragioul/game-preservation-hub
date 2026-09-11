import base64

from app.protocol.protobuf import field_bytes, field_text, field_varint


def build_area() -> bytes:
    return b"".join(
        (
            field_varint(1, 1),
            field_text(2, "http://10.0.2.2:23101/"),
            field_varint(3, 2),
            field_varint(4, 2),
        )
    )


def build_area_ret() -> bytes:
    return b"".join(
        (
            field_varint(1, 200),
            field_text(2, "ok"),
            field_varint(3, 7),
            field_bytes(4, build_area()),
        )
    )


AREA_RESPONSE_TEXT = base64.b64encode(build_area_ret()).decode("ascii")
