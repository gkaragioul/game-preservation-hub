from dataclasses import dataclass
import struct
from datetime import datetime, timedelta, timezone

from app.models.save import LocalProfile
from app.protocol.protobuf import (
    encode_varint,
    field_bytes,
    field_text,
    field_varint,
)
from app.protocol.roguelike_exports import REVIVE_DIVISOR


def pack_frame(net_id: int, payload: bytes) -> bytes:
    return struct.pack(">IH", len(payload) + 6, net_id) + payload


def unpack_frame(frame: bytes) -> tuple[int, bytes]:
    if len(frame) < 6:
        raise ValueError("logic frame is shorter than six-byte header")
    declared, net_id = struct.unpack(">IH", frame[:6])
    if declared != len(frame):
        raise ValueError("logic frame length mismatch")
    return net_id, frame[6:]


def _build_part_container(part_id: int) -> bytes:
    return field_varint(1, part_id) + field_bytes(2, field_varint(1, 1))


def _build_toy_top(parts: tuple[int, int, int]) -> bytes:
    return b"".join(
        field_varint(number, part_id)
        for number, part_id in enumerate(parts, start=1)
    )


def _build_main_lineup() -> bytes:
    tops = ((2001, 2002, 2003), (2004, 2005, 2006), (2028, 2029, 2030))
    lineup = b"".join(
        field_bytes(
            1,
            field_varint(1, index) + field_bytes(2, _build_toy_top(parts)),
        )
        for index, parts in enumerate(tops, start=1)
    )
    lineup += field_varint(2, 1) + field_varint(3, 1) + field_varint(5, 0)
    return field_varint(1, 1) + field_bytes(2, lineup)


def build_base_info(profile: LocalProfile) -> bytes:
    return b"".join(
        (
            field_varint(1, profile.player_id),
            field_text(2, profile.nickname),
            field_varint(3, profile.level),
            field_varint(4, profile.currency.gems),
            field_varint(5, profile.currency.coins),
            field_varint(6, 100),
            field_varint(7, profile.experience),
            field_text(10, "Offline"),
            *(
                field_bytes(15, _build_part_container(part_id))
                for part_id in (2001, 2004, 2028)
            ),
            *(
                field_bytes(16, _build_part_container(part_id))
                for part_id in (2002, 2005, 2029)
            ),
            *(
                field_bytes(17, _build_part_container(part_id))
                for part_id in (2003, 2006, 2030)
            ),
            *(
                field_bytes(
                    22,
                    field_varint(1, item_id)
                    + field_varint(2, amount),
                )
                for item_id, amount in sorted(profile.default_items.items())
            ),
            field_bytes(23, _build_main_lineup()),
            field_varint(26, 0),
            field_varint(34, 1_700_000_000),
            field_varint(37, 7),
            # The lobby HUD reads PlayerLevel/PlayerExp rather than the
            # Level/Exp counters above; without them getPlayerLv() returns 0
            # and levelDataManager.getItem(0) is null.
            field_varint(70, profile.level),
            field_varint(72, profile.experience),
            field_bytes(74, field_varint(1, 12) + field_varint(2, 1)),
            field_bytes(
                82,
                field_text(1, "GuideGrid: 51412444209")
                + field_text(2, "true"),
            ),
        )
    )


def build_player_data(profile: LocalProfile) -> bytes:
    chapter_results = b"".join(
        field_bytes(6, field_varint(1, key) + field_varint(2, result))
        for key, result in sorted(profile.stage_results.items())
    )
    return (
        field_bytes(1, build_base_info(profile))
        + chapter_results
        + field_varint(9, 64)
        + field_bytes(17, field_varint(3, profile.roguelike_keys))
    )


def build_roguelike_player_delta(profile: LocalProfile) -> bytes:
    default_items = b"".join(
        field_bytes(
            22,
            field_varint(1, item_id) + field_varint(2, amount),
        )
        for item_id, amount in sorted(profile.default_items.items())
    )
    return field_bytes(1, default_items) + field_bytes(
        17, field_varint(3, profile.roguelike_keys)
    )


def _build_int_container(index: int, value: int) -> bytes:
    return field_varint(1, index) + field_varint(2, value)


def _build_roguelike_part(part) -> bytes:
    return (
        field_varint(1, part.level)
        + field_varint(2, part.current_skin)
        + b"".join(
            field_bytes(3, _build_int_container(index, value))
            for index, value in sorted(part.location_kerns.items())
        )
    )


def _build_roguelike_top(top) -> bytes:
    return (
        field_varint(1, top.hp)
        + b"".join(
            field_bytes(2, _build_int_container(buff_id, amount))
            for buff_id, amount in sorted(top.buffs.items())
        )
        + b"".join(
            field_bytes(
                3,
                field_varint(1, part_id)
                + field_bytes(2, _build_roguelike_part(part)),
            )
            for part_id, part in sorted(top.parts.items())
        )
    )


def _build_roguelike_node(node) -> bytes:
    result = field_varint(1, node.status)
    if node.event_id is not None:
        event = field_varint(1, node.event_id) + b"".join(
            field_bytes(2, _build_int_container(index, export))
            for index, export in enumerate(node.location_exports)
        )
        result += field_bytes(2, event)
    return result


def _build_roguelike_record(profile: LocalProfile) -> bytes:
    """RogueLikeRecord - what survives the run it was earned in."""
    return b"".join(
        (
            b"".join(
                field_bytes(4, _build_int_container(level, chapter))
                for level, chapter in sorted(
                    profile.roguelike_cleared_chapters.items()
                )
            ),
            field_varint(5, profile.roguelike_enter_map_num),
        )
    )


def build_roguelike_info(profile: LocalProfile) -> bytes:
    run = profile.roguelike_run
    record = field_bytes(2, _build_roguelike_record(profile))
    if run is None:
        # The record still has to travel: an empty message here is what threw
        # away every cleared chapter the moment a run ended.
        return record
    status = (
        field_varint(1, run.location)
        + field_varint(2, run.main_top)
        + field_varint(3, run.emitter)
        + b"".join(
            field_bytes(
                4,
                field_varint(1, top_index)
                + field_bytes(2, _build_roguelike_top(top)),
            )
            for top_index, top in sorted(run.toy_tops.items())
        )
        + b"".join(
            field_bytes(5, _build_int_container(buff_id, amount))
            for buff_id, amount in sorted(run.event_buffs.items())
        )
    )
    run_map = (
        field_varint(1, run.version)
        + field_bytes(2, status)
        + field_varint(3, run.chapter_id)
        + field_varint(4, run.chapter_level)
        + field_varint(5, run.random_seed)
        + b"".join(
            field_bytes(
                6,
                field_varint(1, location)
                + field_bytes(2, _build_roguelike_node(node)),
            )
            for location, node in sorted(run.nodes.items())
        )
        + field_varint(7, run.map_id)
    )
    return field_bytes(1, run_map) + record


def build_roguelike_response(
    *,
    code: int,
    location: int,
    rewards: tuple[tuple[int, int], ...] = (),
) -> bytes:
    response = field_varint(1, code)
    if code == 31:
        items_detail = b"".join(
            field_bytes(
                1,
                field_varint(1, item_id) + field_varint(2, amount),
            )
            for item_id, amount in rewards
        )
        get_items = field_varint(1, 16) + field_bytes(2, items_detail)
        response += field_bytes(3, get_items)
    response += field_varint(4, location)
    if code == 31:
        response += field_varint(5, -1)
    return response


def build_sc_login(profile: LocalProfile) -> bytes:
    return b"".join(
        (
            field_varint(1, profile.player_id),
            field_varint(2, 1),
            field_varint(4, 1),
            field_varint(6, 1),
            field_varint(8, 1),
            field_text(12, "local-1"),
            field_varint(13, 1),
        )
    )


def build_chapter_result_delta(chapter_key: int, result: int) -> bytes:
    return field_bytes(
        6, field_varint(1, chapter_key) + field_varint(2, result)
    )


def build_chapter_opr_ack(operation: int) -> bytes:
    return field_varint(1, operation)


def build_race_end() -> bytes:
    return field_varint(1, 14)


def _decode_raw_varint(payload: bytes, index: int) -> tuple[int, int]:
    start = index
    value = 0
    for byte_index in range(10):
        if index >= len(payload):
            raise ValueError("truncated protobuf varint")
        byte = payload[index]
        index += 1
        if byte_index == 9 and byte > 1:
            raise ValueError("protobuf varint exceeds uint64")
        value |= (byte & 0x7F) << (byte_index * 7)
        if byte < 0x80:
            if payload[start:index] != encode_varint(value):
                raise ValueError("protobuf varint is not canonical")
            return value, index
    raise ValueError("invalid protobuf varint")


def decode_varint(payload: bytes, index: int) -> tuple[int, int]:
    return _decode_raw_varint(payload, index)


def decode_canonical_int32(
    payload: bytes, index: int
) -> tuple[int, int]:
    raw_value, index = _decode_raw_varint(payload, index)
    if raw_value <= 0x7FFF_FFFF:
        return raw_value, index
    if raw_value < 0xFFFF_FFFF_8000_0000:
        raise ValueError("protobuf int32 value is outside its canonical width")
    return raw_value - (1 << 64), index


def decode_canonical_int64(
    payload: bytes, index: int
) -> tuple[int, int]:
    raw_value, index = _decode_raw_varint(payload, index)
    if raw_value <= 0x7FFF_FFFF_FFFF_FFFF:
        return raw_value, index
    return raw_value - (1 << 64), index


@dataclass(frozen=True)
class ChapterOperation:
    operation: int
    chapter_key: int
    chapter_version: int | None
    result: int | None
    self_win_num: int | None
    use_parts: tuple[int, ...]


def parse_chapter_operation(payload: bytes) -> ChapterOperation:
    index = 0
    scalar_fields: dict[int, int] = {}
    use_parts: list[int] = []
    while index < len(payload):
        key, index = decode_varint(payload, index)
        field_number, wire_type = key >> 3, key & 7
        if field_number == 0:
            raise ValueError("protobuf field number cannot be zero")
        if field_number in (1, 2, 3, 4, 5):
            if wire_type != 0:
                raise ValueError("chapter scalar field has unsupported wire type")
            if field_number in scalar_fields:
                raise ValueError("chapter scalar field is duplicated")
            width = 64 if field_number == 3 else 32
            if width == 64:
                value, index = decode_canonical_int64(payload, index)
            else:
                value, index = decode_canonical_int32(payload, index)
            scalar_fields[field_number] = value
            continue
        if field_number == 6:
            if wire_type == 0:
                value, index = decode_canonical_int32(payload, index)
                use_parts.append(value)
                continue
            if wire_type != 2:
                raise ValueError("chapter parts field has unsupported wire type")
            size, index = decode_varint(payload, index)
            end = index + size
            if end > len(payload):
                raise ValueError("truncated packed chapter parts")
            packed_parts = payload[index:end]
            index = end
            packed_index = 0
            while packed_index < len(packed_parts):
                value, packed_index = decode_canonical_int32(
                    packed_parts, packed_index
                )
                use_parts.append(value)
            continue
        raise ValueError("unsupported chapter protobuf field")
    if 1 not in scalar_fields or 2 not in scalar_fields:
        raise ValueError("chapter operation and key are required")
    return ChapterOperation(
        operation=scalar_fields[1],
        chapter_key=scalar_fields[2],
        chapter_version=scalar_fields.get(3),
        result=scalar_fields.get(4),
        self_win_num=scalar_fields.get(5),
        use_parts=tuple(use_parts),
    )


@dataclass(frozen=True)
class RogueLikeRequestEvent:
    event_id: int
    location_exports: tuple[int, ...]


@dataclass(frozen=True)
class RogueLikeRequestNode:
    location: int
    event: RogueLikeRequestEvent | None


@dataclass(frozen=True)
class RogueLikeRequestToyTop:
    hp: int
    buffs: tuple[int, ...]


@dataclass(frozen=True)
class RogueLikeEnterMapRequest:
    roguelike_version: int
    chapter_id: int
    chapter_level: int
    seed: int
    init_node: RogueLikeRequestNode
    init_toy_tops: tuple[RogueLikeRequestToyTop, ...]
    is_buy_key: int
    map_id: int
    node_distribute: tuple[tuple[int, int], ...] | None
    cost_key: int


@dataclass(frozen=True)
class RogueLikeEnterNodeRequest:
    roguelike_version: int
    new_node: RogueLikeRequestNode
    refresh_node: int
    chapter_id: int


@dataclass(frozen=True)
class RogueLikeMiscOprRequest:
    roguelike_version: int
    opr_type: int
    param: int | None
    chapter_id: int | None


@dataclass(frozen=True)
class RogueLikeTriggerRequest:
    roguelike_version: int
    cur_node: RogueLikeRequestNode
    trigger_path: tuple[int, ...]
    trigger_location: int
    now_toy_tops: tuple[RogueLikeRequestToyTop, ...]
    trigger_all_node: int
    energy_type: int
    use_buff: int | None
    clear_next_battle_buff: int
    refresh_times: int | None
    bargain_times: int | None
    steal_times: int | None
    discount_list: tuple[int, ...]
    discount_list_present: bool
    is_steal: int | None
    chapter_id: int


class _ProtoReader:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.index = 0

    @property
    def done(self) -> bool:
        return self.index == len(self.payload)

    def key(self) -> tuple[int, int]:
        key, self.index = decode_varint(self.payload, self.index)
        number = key >> 3
        if number == 0:
            raise ValueError("protobuf field number cannot be zero")
        return number, key & 7

    def int32(self) -> int:
        value, self.index = decode_canonical_int32(
            self.payload, self.index
        )
        return value

    def bytes(self) -> bytes:
        size, self.index = decode_varint(self.payload, self.index)
        end = self.index + size
        if end > len(self.payload):
            raise ValueError("truncated length-delimited protobuf field")
        result = self.payload[self.index:end]
        self.index = end
        return result


def _set_scalar(
    fields: dict[int, int], number: int, reader: _ProtoReader
) -> None:
    if number in fields:
        raise ValueError(f"duplicate protobuf scalar field {number}")
    fields[number] = reader.int32()


def _append_repeated_int32(
    values: list[int], wire_type: int, reader: _ProtoReader
) -> None:
    if wire_type == 0:
        values.append(reader.int32())
        return
    if wire_type != 2:
        raise ValueError("repeated int32 has unsupported wire type")
    packed = _ProtoReader(reader.bytes())
    while not packed.done:
        values.append(packed.int32())


def _parse_request_event(payload: bytes) -> RogueLikeRequestEvent:
    reader = _ProtoReader(payload)
    scalars: dict[int, int] = {}
    exports: list[int] = []
    while not reader.done:
        number, wire_type = reader.key()
        if number == 1:
            if wire_type != 0:
                raise ValueError("event id has unsupported wire type")
            _set_scalar(scalars, number, reader)
        elif number == 2:
            _append_repeated_int32(exports, wire_type, reader)
        else:
            raise ValueError("unsupported RogueLike event field")
    if 1 not in scalars:
        raise ValueError("RogueLike event id is required")
    return RogueLikeRequestEvent(scalars[1], tuple(exports))


def _parse_request_node(payload: bytes) -> RogueLikeRequestNode:
    reader = _ProtoReader(payload)
    location: int | None = None
    event: RogueLikeRequestEvent | None = None
    while not reader.done:
        number, wire_type = reader.key()
        if number == 1:
            if wire_type != 0 or location is not None:
                raise ValueError("invalid or duplicate RogueLike node location")
            location = reader.int32()
        elif number == 2:
            if wire_type != 2 or event is not None:
                raise ValueError("invalid or duplicate RogueLike node event")
            event = _parse_request_event(reader.bytes())
        else:
            raise ValueError("unsupported RogueLike node field")
    if location is None:
        raise ValueError("RogueLike node location is required")
    return RogueLikeRequestNode(location, event)


def _parse_request_top(payload: bytes) -> RogueLikeRequestToyTop:
    reader = _ProtoReader(payload)
    hp: int | None = None
    buffs: list[int] = []
    while not reader.done:
        number, wire_type = reader.key()
        if number == 1:
            if wire_type != 0 or hp is not None:
                raise ValueError("invalid or duplicate RogueLike top hp")
            hp = reader.int32()
        elif number == 2:
            _append_repeated_int32(buffs, wire_type, reader)
        else:
            raise ValueError("unsupported RogueLike top field")
    if hp is None:
        raise ValueError("RogueLike top hp is required")
    return RogueLikeRequestToyTop(hp, tuple(buffs))


def _parse_int_map_entry(payload: bytes) -> tuple[int, int]:
    reader = _ProtoReader(payload)
    fields: dict[int, int] = {}
    while not reader.done:
        number, wire_type = reader.key()
        if number not in (1, 2) or wire_type != 0:
            raise ValueError("unsupported RogueLike map entry field")
        _set_scalar(fields, number, reader)
    if set(fields) != {1, 2}:
        raise ValueError("RogueLike map entry key and value are required")
    return fields[1], fields[2]


def parse_roguelike_enter_map(payload: bytes) -> RogueLikeEnterMapRequest:
    outer = _ProtoReader(payload)
    outer_version: int | None = None
    enter_map_payload: bytes | None = None
    while not outer.done:
        number, wire_type = outer.key()
        if number == 1:
            if wire_type != 0 or outer_version is not None:
                raise ValueError("invalid or duplicate RogueLike version")
            outer_version = outer.int32()
        elif number == 2:
            if wire_type != 2 or enter_map_payload is not None:
                raise ValueError("invalid or duplicate EnterMap payload")
            enter_map_payload = outer.bytes()
        else:
            raise ValueError("unsupported CS_RogueLikeEnterMap field")
    if outer_version is None or enter_map_payload is None:
        raise ValueError("RogueLike version and EnterMap are required")

    reader = _ProtoReader(enter_map_payload)
    scalars: dict[int, int] = {}
    init_node: RogueLikeRequestNode | None = None
    tops: list[RogueLikeRequestToyTop] = []
    node_distribute: list[tuple[int, int]] | None = None
    while not reader.done:
        number, wire_type = reader.key()
        if number in (1, 2, 3, 6, 7, 9):
            if wire_type != 0:
                raise ValueError("EnterMap scalar has unsupported wire type")
            _set_scalar(scalars, number, reader)
        elif number == 4:
            if wire_type != 2 or init_node is not None:
                raise ValueError("invalid or duplicate EnterMap InitNode")
            init_node = _parse_request_node(reader.bytes())
        elif number == 5:
            if wire_type != 2:
                raise ValueError("EnterMap top has unsupported wire type")
            tops.append(_parse_request_top(reader.bytes()))
        elif number == 8:
            if wire_type != 2:
                raise ValueError("EnterMap map entry has unsupported wire type")
            if node_distribute is None:
                node_distribute = []
            entry = _parse_int_map_entry(reader.bytes())
            if any(key == entry[0] for key, _ in node_distribute):
                raise ValueError("duplicate EnterMap map key")
            node_distribute.append(entry)
        else:
            raise ValueError("unsupported EnterMap field")
    if set(scalars) != {1, 2, 3, 6, 7, 9} or init_node is None:
        raise ValueError("EnterMap required fields are missing")
    return RogueLikeEnterMapRequest(
        outer_version,
        scalars[1],
        scalars[2],
        scalars[3],
        init_node,
        tuple(tops),
        scalars[6],
        scalars[7],
        None if node_distribute is None else tuple(node_distribute),
        scalars[9],
    )


def parse_roguelike_enter_node(payload: bytes) -> RogueLikeEnterNodeRequest:
    outer = _ProtoReader(payload)
    version: int | None = None
    enter_node_payload: bytes | None = None
    chapter_id: int | None = None
    while not outer.done:
        number, wire_type = outer.key()
        if number == 1:
            if wire_type != 0 or version is not None:
                raise ValueError("invalid or duplicate RogueLike version")
            version = outer.int32()
        elif number == 2:
            if wire_type != 2 or enter_node_payload is not None:
                raise ValueError("invalid or duplicate EnterNode payload")
            enter_node_payload = outer.bytes()
        elif number == 3:
            if wire_type != 0 or chapter_id is not None:
                raise ValueError("invalid or duplicate RogueLike chapter")
            chapter_id = outer.int32()
        else:
            raise ValueError("unsupported CS_RogueLikeEnterNode field")
    if version is None or enter_node_payload is None or chapter_id is None:
        raise ValueError("EnterNode outer required fields are missing")

    reader = _ProtoReader(enter_node_payload)
    new_node: RogueLikeRequestNode | None = None
    refresh_node: int | None = None
    while not reader.done:
        number, wire_type = reader.key()
        if number == 1:
            if wire_type != 2 or new_node is not None:
                raise ValueError("invalid or duplicate EnterNode node")
            new_node = _parse_request_node(reader.bytes())
        elif number == 2:
            if wire_type != 0 or refresh_node is not None:
                raise ValueError("invalid or duplicate EnterNode refresh")
            refresh_node = reader.int32()
        else:
            raise ValueError("unsupported EnterNode field")
    if new_node is None or refresh_node is None:
        raise ValueError("EnterNode required fields are missing")
    return RogueLikeEnterNodeRequest(
        version, new_node, refresh_node, chapter_id
    )


# RogueLikeMiscOprType values recovered from the decrypted bundle. Only the
# postbattle selection is modelled; the rest stay unhandled rather than
# answered with a fabricated success.
RL_MISC_OPR_EXCHANGE_KEY = 1
RL_MISC_OPR_GIVE_UP_MAP = 2
RL_MISC_OPR_BATTLE_OVER_SELECT = 3
RL_MISC_OPR_BATTLE_FAILED = 14

# Adventure keys the client shows as x/8.
ROGUELIKE_KEY_CAP = 8

# RogueLikeMap.Version is a map timestamp, not a counter: the client feeds it
# to getRealTime(), which is `new Date(getDateTime2018() + 1000 * Version)`
# with getDateTime2018 fixed at 2018-01-01T00:00:00+08:00. loadLocalStorage()
# abandons the run when that lands before minMapVersion (2020-07-16), and
# checkTimeOver() reads Version + keepHours as the expiry.
ROGUELIKE_MAP_EPOCH = datetime(
    2018, 1, 1, tzinfo=timezone(timedelta(hours=8))
)


def map_version_now() -> int:
    """Seconds since the client's 2018 map epoch."""
    return int(
        (datetime.now(timezone.utc) - ROGUELIKE_MAP_EPOCH).total_seconds()
    )

# ERogueLikeCode values
ROGUELIKE_EXCHANGE_KEY_SUCCESS = 50
ROGUELIKE_GIVE_UP_MAP_SUCCESS = 60
ROGUELIKE_BATTLE_OVER_SELECT_SUCCESS = 61


def claim_hp_effect(selected_export: int, prior_hp: int) -> int:
    """Apply the postbattle export's healing effect to one top."""
    if selected_export == 100069:
        return (11 * prior_hp + 9) // 10
    if selected_export == 100077:
        return (6 * prior_hp + 4) // 5
    return prior_hp


def repair_hp_effect(prior_hp: int, max_hp: int, export_num: int) -> int:
    """What a repair station leaves a top on, per the client's own dealHp.

    `setChijiItem` calls `dealHp(ExportNum / 100, index, true)`, which halves
    the ratio for a defeated top and rounds the result up. It applies this
    before sending, so the confirm carries the healed value rather than the
    one the gateway holds - and it does not clamp: `getToyTopMaxHp` clamps
    the client's own copy afterwards, which is why the stored value is.
    """
    divisor = 100 * (REVIVE_DIVISOR if prior_hp <= 0 else 1)
    return prior_hp + -(-max_hp * export_num // divisor)


def parse_roguelike_misc_opr(payload: bytes) -> RogueLikeMiscOprRequest:
    """Parse CS_RogueLikeMiscOpr.

    ``CS_RogueLikeMiscOpr{1 RogueLikeVersion, 2 MiscOpr, 3 chapterId}`` wraps
    ``RogueLikeMiscOpr{1 OprType, 2 param}``. ``RogueLike_BattleOverSelect``
    sets the version and the inner pair and leaves ``chapterId`` unset.
    """
    outer = _ProtoReader(payload)
    version: int | None = None
    misc_payload: bytes | None = None
    chapter_id: int | None = None
    while not outer.done:
        number, wire_type = outer.key()
        if number == 1:
            if wire_type != 0 or version is not None:
                raise ValueError("invalid or duplicate RogueLike version")
            version = outer.int32()
        elif number == 2:
            if wire_type != 2 or misc_payload is not None:
                raise ValueError("invalid or duplicate MiscOpr payload")
            misc_payload = outer.bytes()
        elif number == 3:
            if wire_type != 0 or chapter_id is not None:
                raise ValueError("invalid or duplicate MiscOpr chapter")
            chapter_id = outer.int32()
        else:
            raise ValueError("unsupported CS_RogueLikeMiscOpr field")
    if version is None or misc_payload is None:
        raise ValueError("RogueLike version and MiscOpr are required")

    reader = _ProtoReader(misc_payload)
    opr_type: int | None = None
    param: int | None = None
    while not reader.done:
        number, wire_type = reader.key()
        if wire_type != 0:
            raise ValueError("MiscOpr field has unsupported wire type")
        if number == 1:
            if opr_type is not None:
                raise ValueError("duplicate MiscOpr OprType")
            opr_type = reader.int32()
        elif number == 2:
            if param is not None:
                raise ValueError("duplicate MiscOpr param")
            param = reader.int32()
        else:
            raise ValueError("unsupported RogueLikeMiscOpr field")
    if opr_type is None:
        raise ValueError("MiscOpr OprType is required")
    return RogueLikeMiscOprRequest(
        roguelike_version=version,
        opr_type=opr_type,
        param=param,
        chapter_id=chapter_id,
    )


def parse_roguelike_trigger(payload: bytes) -> RogueLikeTriggerRequest:
    outer = _ProtoReader(payload)
    version: int | None = None
    trigger_payload: bytes | None = None
    chapter_id: int | None = None
    while not outer.done:
        number, wire_type = outer.key()
        if number == 1:
            if wire_type != 0 or version is not None:
                raise ValueError("invalid or duplicate RogueLike version")
            version = outer.int32()
        elif number == 2:
            if wire_type != 2 or trigger_payload is not None:
                raise ValueError("invalid or duplicate Trigger payload")
            trigger_payload = outer.bytes()
        elif number == 3:
            if wire_type != 0 or chapter_id is not None:
                raise ValueError("invalid or duplicate RogueLike chapter")
            chapter_id = outer.int32()
        else:
            raise ValueError("unsupported CS_RogueLikeTrigger field")
    if version is None or trigger_payload is None or chapter_id is None:
        raise ValueError("Trigger outer required fields are missing")

    reader = _ProtoReader(trigger_payload)
    node: RogueLikeRequestNode | None = None
    paths: list[int] = []
    tops: list[RogueLikeRequestToyTop] = []
    discounts: list[int] = []
    discount_list_present = False
    scalars: dict[int, int] = {}
    while not reader.done:
        number, wire_type = reader.key()
        if number == 1:
            if wire_type != 2 or node is not None:
                raise ValueError("invalid or duplicate Trigger node")
            node = _parse_request_node(reader.bytes())
        elif number == 2:
            _append_repeated_int32(paths, wire_type, reader)
        elif number == 4:
            if wire_type != 2:
                raise ValueError("Trigger top has unsupported wire type")
            tops.append(_parse_request_top(reader.bytes()))
        elif number == 12:
            discount_list_present = True
            _append_repeated_int32(discounts, wire_type, reader)
        elif number in (3, 5, 6, 7, 8, 9, 10, 11, 13):
            if wire_type != 0:
                raise ValueError("Trigger scalar has unsupported wire type")
            _set_scalar(scalars, number, reader)
        else:
            raise ValueError("unsupported Trigger field")
    if node is None or not {3, 5, 6, 8}.issubset(scalars):
        raise ValueError("Trigger required fields are missing")
    return RogueLikeTriggerRequest(
        version,
        node,
        tuple(paths),
        scalars[3],
        tuple(tops),
        scalars[5],
        scalars[6],
        scalars.get(7),
        scalars[8],
        scalars.get(9),
        scalars.get(10),
        scalars.get(11),
        tuple(discounts),
        discount_list_present,
        scalars.get(13),
        chapter_id,
    )


def parse_report_status(payload: bytes) -> int:
    index = 0
    if not payload:
        raise ValueError("report status is required")
    key, index = decode_varint(payload, index)
    if key != 8:
        raise ValueError("report status field has unsupported wire type")
    status, index = decode_canonical_int32(payload, index)
    if index != len(payload):
        raise ValueError("report status contains unexpected fields")
    return status


# CS_LoginNode field number -> declared wire type, taken from the generated
# encoder in the decrypted bundle. The shipped CN client emits every field
# except devImei (8), so accepting only field 1 rejects every real login.
LOGIN_NODE_FIELDS = {
    1: 2,  # logicToken   string
    2: 0,  # reLoginKey   int64
    3: 2,  # PhoneCode    string
    4: 0,  # clientType   int32
    5: 2,  # fromCh       string
    6: 2,  # adChannel    string
    7: 2,  # adSubchannel string
    8: 2,  # devImei      string
    9: 0,  # language     int32
    10: 2,  # devOs        string
    11: 0,  # accountId    int64
    12: 2,  # checkVersion string
}
LOGIN_TOKEN_FIELD = 1


def parse_login_token(payload: bytes) -> str:
    """Return ``logicToken`` from a CS_LoginNode frame.

    Every declared field is accepted with its declared wire type. An
    undeclared field number, a declared field carrying the wrong wire type, a
    duplicate, or a truncated value is rejected, so an unexpected client build
    cannot authenticate by accident.
    """
    index = 0
    token: bytes | None = None
    seen: set[int] = set()
    while index < len(payload):
        key, index = decode_varint(payload, index)
        field_number, wire_type = key >> 3, key & 7
        declared = LOGIN_NODE_FIELDS.get(field_number)
        if declared is None:
            raise ValueError(
                f"CS_LoginNode has undeclared field {field_number}"
            )
        if wire_type != declared:
            raise ValueError(
                f"CS_LoginNode field {field_number} declares wire type "
                f"{declared}, got {wire_type}"
            )
        if field_number in seen:
            raise ValueError(f"duplicate protobuf field {field_number}")
        seen.add(field_number)
        if wire_type == 0:
            _, index = decode_varint(payload, index)
            continue
        length, index = decode_varint(payload, index)
        value = payload[index : index + length]
        if len(value) != length:
            raise ValueError("truncated protobuf field")
        index += length
        if field_number == LOGIN_TOKEN_FIELD:
            token = value
    if token is None:
        raise ValueError("CS_LoginNode is missing logicToken")
    return token.decode("utf-8")
