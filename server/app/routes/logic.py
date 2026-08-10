import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.save import (
    RogueLikeNodeState,
    RogueLikePartState,
    RogueLikeRunState,
    RogueLikeToyTopState,
)
from app.protocol.logic import (
    RL_MISC_OPR_BATTLE_FAILED,
    RL_MISC_OPR_BATTLE_OVER_SELECT,
    RL_MISC_OPR_EXCHANGE_KEY,
    RL_MISC_OPR_GIVE_UP_MAP,
    ROGUELIKE_BATTLE_OVER_SELECT_SUCCESS,
    ROGUELIKE_EXCHANGE_KEY_SUCCESS,
    ROGUELIKE_KEY_CAP,
    ROGUELIKE_GIVE_UP_MAP_SUCCESS,
    RogueLikeEnterMapRequest,
    RogueLikeEnterNodeRequest,
    RogueLikeMiscOprRequest,
    RogueLikeTriggerRequest,
    claim_hp_effect,
    map_version_now,
    repair_hp_effect,
    build_chapter_opr_ack,
    build_chapter_result_delta,
    build_player_data,
    build_race_end,
    build_roguelike_info,
    build_roguelike_player_delta,
    build_roguelike_response,
    build_sc_login,
    pack_frame,
    parse_login_token,
    parse_chapter_operation,
    parse_roguelike_enter_map,
    parse_roguelike_enter_node,
    parse_roguelike_misc_opr,
    parse_roguelike_trigger,
    parse_report_status,
    unpack_frame,
)
from app.protocol.roguelike_events import (
    REWARD_EVENT,
    SELECT_EVENT,
    event_type,
    is_boss_event,
    is_declared_event,
    is_fightable_event,
    fixed_exports,
    random_export_count,
)
from app.protocol.roguelike_exports import (
    CHIJI_ITEM_REWARD,
    ITEM_REWARD,
    RECOVER_HP_REWARD,
    reward_export,
    select_export,
)
from app.security.logic_token import verify_logic_token
from app.storage.profile_store import (
    ProfileStore,
    profile_transaction,
    runtime_save_dir,
)

router = APIRouter()
POSTBATTLE_EXPORTS = {
    100066: 4201,
    100067: 4202,
    100068: 4203,
    100069: 4204,
    100070: 4205,
    100071: 4206,
    100072: 4207,
    100073: 4208,
    100074: 4209,
    100075: 4210,
    100076: 4211,
    100077: 4212,
    100078: 4221,
    100079: 4222,
    100081: 4224,
    100082: 4225,
    100083: 4226,
    100084: 4227,
    100085: 4228,
    100088: 4231,
}


def _journal(
    direction: str,
    net_id: int,
    known: bool,
    chapter_version: int | None = None,
    roguelike_version: int | None = None,
    chapter_id: int | None = None,
    location: int | None = None,
    event_id: int | None = None,
    location_exports: tuple[int, ...] | None = None,
    trigger_path: tuple[int, ...] | None = None,
    toy_tops: tuple[object, ...] | None = None,
) -> None:
    path = runtime_save_dir() / "logic-frames.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        entry: dict[str, object] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "net_id": net_id,
            "known": known,
        }
        if chapter_version is not None:
            entry["chapter_version"] = chapter_version
        if roguelike_version is not None:
            entry["roguelike_version"] = roguelike_version
        if chapter_id is not None:
            entry["chapter_id"] = chapter_id
        if location is not None:
            entry["location"] = location
        if event_id is not None:
            entry["event_id"] = event_id
        if location_exports:
            # A refused request is answered by closing, so the exports it
            # offered are the only way to tell a permutation from a bad count.
            entry["location_exports"] = list(location_exports)
        if trigger_path:
            entry["trigger_path"] = list(trigger_path)
        if toy_tops:
            entry["toy_tops"] = [
                (
                    {"hp": top.hp, "buffs": list(top.buffs)}
                    if top.buffs
                    else {"hp": top.hp}
                )
                for top in toy_tops
            ]
        handle.write(json.dumps(entry) + "\n")


def _enter_map_frames(
    account_id: str, request: RogueLikeEnterMapRequest
) -> tuple[tuple[int, bytes], ...] | None:
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        # The client shows a daily refresh countdown for adventure keys, but
        # the local service never granted any, so the count could only fall
        # and the mode became unplayable once the starting key was spent.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if (
            profile.roguelike_keys < 1
            and profile.roguelike_keys_refreshed_on != today
        ):
            profile.roguelike_keys = ROGUELIKE_KEY_CAP
            profile.roguelike_keys_refreshed_on = today
            store.save(profile)
        if (
            request.roguelike_version != 0
            or request.chapter_id != -1
            or request.chapter_level != 1
            or not 0 <= request.seed <= 157_599_999
            or request.init_node.location != 3
            or request.init_node.event is not None
            or len(request.init_toy_tops) != 3
            or any(
                top.hp <= 0 or top.buffs
                for top in request.init_toy_tops
            )
            or request.is_buy_key != 0
            or request.map_id != 0
            or request.node_distribute is not None
            or request.cost_key != 1
            or profile.roguelike_run is not None
            or profile.roguelike_keys < 1
        ):
            return None
        part_ids = {
            1: (2001, 2002, 2003),
            2: (2004, 2005, 2006),
            3: (2028, 2029, 2030),
        }
        tops = {
            index: RogueLikeToyTopState(
                hp=top.hp,
                max_hp=top.hp,
                parts={
                    part_id: RogueLikePartState()
                    for part_id in part_ids[index]
                },
            )
            for index, top in enumerate(request.init_toy_tops, start=1)
        }
        profile.roguelike_keys -= 1
        profile.roguelike_enter_map_num += 1
        profile.roguelike_run = RogueLikeRunState(
            version=map_version_now(),
            random_seed=request.seed,
            toy_tops=tops,
        )
        store.save(profile)
        return (
            (5, build_roguelike_info(profile)),
            (1, build_roguelike_player_delta(profile)),
            (
                180,
                build_roguelike_response(
                    code=10, location=request.init_node.location
                ),
            ),
        )


def _enter_node_frames(
    account_id: str, request: RogueLikeEnterNodeRequest
) -> tuple[tuple[int, bytes], ...] | None:
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        run = profile.roguelike_run
        if (
            run is None
            or request.roguelike_version != run.version
            or request.chapter_id != run.chapter_id
        ):
            return None
        if request.new_node.location == 3:
            existing = run.nodes.get(3)
            if (
                request.new_node.event is not None
                or request.refresh_node != 0
                or run.location != 3
                or (existing is not None and existing.status != 0)
            ):
                return None
            run.nodes[3] = RogueLikeNodeState(status=3)
            run.location = 3
        elif request.new_node.location == 10003:
            start = run.nodes.get(3)
            story = run.nodes.get(10003)
            event = request.new_node.event
            if event is None:
                return None
            if event.event_id == 110000:
                if (
                    request.refresh_node != 0
                    or run.location != 3
                    or event.location_exports
                    or start is None
                    or start.status != 3
                    or (story is not None and story.status != 0)
                ):
                    return None
                run.nodes[10003] = RogueLikeNodeState(
                    status=1, event_id=110000
                )
            elif event.event_id == 110019:
                # The branch's three choices are declared in data/RogueLike,
                # so `setEvent` fills them in client side and the request
                # carries none. Anything else is not this branch.
                declared = fixed_exports(110019)
                if (
                    request.refresh_node != 1
                    or event.location_exports
                    or story is None
                    or story.status != 1
                    or story.event_id != 110000
                    or story.location_exports
                    or run.location != 10003
                ):
                    return None
                story.event_id = 110019
                story.location_exports = list(declared)
            elif event.event_id == 110005:
                if (
                    request.refresh_node != 1
                    or event.location_exports
                    or story is None
                    or story.status != 1
                    or story.event_id != 110000
                    or story.location_exports
                    or run.location != 10003
                ):
                    return None
                story.event_id = 110005
            else:
                return None
            run.location = 10003
        elif is_fightable_event(
            request.new_node.event.event_id
            if request.new_node.event is not None
            else 0
        ):
            # Battle nodes are recognised by their declared event type, not by
            # a fixed location or id: the prologue alone has two of them under
            # different ids, and keying on the id stranded a run after the
            # first. The client owns the map layout, so the reachable check is
            # that we are standing on a completed node and the target is new.
            current = run.nodes.get(run.location)
            battle = run.nodes.get(request.new_node.location)
            event = request.new_node.event
            assert event is not None
            # How many exports the client rolled is declared per event, not
            # per kind: the boss draws four where a battle draws three.
            rolled = random_export_count(event.event_id)
            if (
                request.refresh_node != 0
                or rolled < 1
                or len(event.location_exports) != rolled
                or len(set(event.location_exports)) != rolled
                or any(export <= 0 for export in event.location_exports)
                or current is None
                or current.status != 3
                or run.location == request.new_node.location
                or (battle is not None and battle.status != 0)
            ):
                return None
            run.nodes[request.new_node.location] = RogueLikeNodeState(
                status=1,
                event_id=event.event_id,
                location_exports=list(event.location_exports),
            )
            run.location = request.new_node.location
        elif is_declared_event(
            request.new_node.event.event_id
            if request.new_node.event is not None
            else 0
        ):
            # Every other declared node kind - reward, select, shop, talk -
            # is entered the same way; only resolving it differs. Refusing
            # entry is what strands a run, so entry is allowed even where the
            # trigger is not modelled yet.
            current = run.nodes.get(run.location)
            target = run.nodes.get(request.new_node.location)
            event = request.new_node.event
            assert event is not None
            if (
                request.refresh_node != 0
                or current is None
                or current.status != 3
                or run.location == request.new_node.location
                or (target is not None and target.status != 0)
            ):
                return None
            run.nodes[request.new_node.location] = RogueLikeNodeState(
                status=1,
                event_id=event.event_id,
                location_exports=list(event.location_exports),
            )
            run.location = request.new_node.location
        else:
            return None
        store.save(profile)
        return (
            (5, build_roguelike_info(profile)),
            (
                180,
                build_roguelike_response(code=20, location=run.location),
            ),
        )


def _exchange_key_frames(
    account_id: str, request: RogueLikeMiscOprRequest
) -> tuple[tuple[int, bytes], ...] | None:
    """Refill one adventure key.

    The retired service charged for this from a live price table. Offline the
    lab grants the key outright rather than inventing a price: the currency it
    would have cost is local-only, while the protocol contract the client
    checks is the ExchangeKeySuccess code.
    """
    if request.param is not None or request.chapter_id is not None:
        return None
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        if profile.roguelike_keys >= ROGUELIKE_KEY_CAP:
            return None
        profile.roguelike_keys += 1
        store.save(profile)
        return (
            (5, build_roguelike_info(profile)),
            (
                180,
                build_roguelike_response(
                    code=ROGUELIKE_EXCHANGE_KEY_SUCCESS,
                    location=(
                        0
                        if profile.roguelike_run is None
                        else profile.roguelike_run.location
                    ),
                ),
            ),
        )


def _give_up_map_frames(
    account_id: str, request: RogueLikeMiscOprRequest
) -> tuple[tuple[int, bytes], ...] | None:
    """Abandon the active run.

    The client sends RL_MiscOpr_GiveUpMap whenever it cannot resume a map,
    including a run whose postbattle reward was never claimed. Refusing it
    strands the player on the map screen with no way out. The key spent to
    open the map is not refunded.
    """
    if request.param is not None:
        return None
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        run = profile.roguelike_run
        if run is None or request.roguelike_version != run.version:
            return None
        location = run.location
        profile.roguelike_run = None
        store.save(profile)
        return (
            (5, build_roguelike_info(profile)),
            (
                180,
                build_roguelike_response(
                    code=ROGUELIKE_GIVE_UP_MAP_SUCCESS,
                    location=location,
                ),
            ),
        )


def _battle_over_select_frames(
    account_id: str, request: RogueLikeMiscOprRequest
) -> tuple[tuple[int, bytes], ...] | None:
    """Claim the postbattle chip selected through CS_RogueLikeMiscOpr.

    ``RogueLike_BattleOverSelect`` is how the live client claims the reward
    after a won battle; it carries the chosen export in ``param`` and expects
    ``SC_RogueLikeRet`` code 61. Every other operation type stays unmodelled.
    """
    if request.opr_type == RL_MISC_OPR_EXCHANGE_KEY:
        return _exchange_key_frames(account_id, request)
    if request.opr_type in (
        RL_MISC_OPR_GIVE_UP_MAP,
        RL_MISC_OPR_BATTLE_FAILED,
    ):
        # Both end the run. RogueLike_BattleFailEx and RogueLike_GiveupEx
        # differ only in the operation type they report - each emits
        # MapClose client side - and ERogueLikeCode carries no
        # failure-specific result, so both are answered with
        # GiveUpMapSuccess.
        return _give_up_map_frames(account_id, request)
    if request.opr_type != RL_MISC_OPR_BATTLE_OVER_SELECT:
        return None
    if request.param is None or request.chapter_id is not None:
        return None
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        run = profile.roguelike_run
        if run is None or request.roguelike_version != run.version:
            return None
        node = run.nodes.get(run.location)
        if (
            node is None
            or node.status != 2
            or node.event_id != 110001
            or not run.pending_battle_reward
            or request.param not in POSTBATTLE_EXPORTS
        ):
            return None
        selected_export = request.param
        for index in (1, 2, 3):
            run.toy_tops[index].hp = claim_hp_effect(
                selected_export, run.toy_tops[index].hp
            )
        selected_buff = POSTBATTLE_EXPORTS[selected_export]
        run.event_buffs[selected_buff] = (
            run.event_buffs.get(selected_buff, 0) + 1
        )
        node.status = 3
        run.pending_battle_reward = False
        store.save(profile)
        return (
            (5, build_roguelike_info(profile)),
            (
                180,
                build_roguelike_response(
                    code=ROGUELIKE_BATTLE_OVER_SELECT_SUCCESS,
                    location=run.location,
                ),
            ),
        )


def _trigger_unsupported_fields_are_absent(
    request: RogueLikeTriggerRequest,
) -> bool:
    return (
        request.use_buff is None
        and request.refresh_times is None
        and request.bargain_times is None
        and request.steal_times is None
        and not request.discount_list_present
        and request.is_steal is None
    )


def _marked_top(request: RogueLikeTriggerRequest) -> tuple[int, int] | None:
    """The (1-based top, export item id) a Select confirm names, if any.

    RogueLike_Trigger_Export_Select is the only sender that fills in a top's
    Buffs, and it fills in exactly one entry on exactly one top. Anything
    else - no mark, two marks, a second id - names no single choice.
    """
    marked = [
        (index, top.buffs)
        for index, top in enumerate(request.now_toy_tops, start=1)
        if top.buffs
    ]
    if len(marked) != 1 or len(marked[0][1]) != 1:
        return None
    index, buffs = marked[0]
    return index, buffs[0]


def _trigger_frames(
    account_id: str, request: RogueLikeTriggerRequest
) -> tuple[tuple[int, bytes], ...] | None:
    with profile_transaction():
        store = ProfileStore()
        profile = store.load(account_id)
        run = profile.roguelike_run
        if (
            run is None
            or request.roguelike_version != run.version
            or request.chapter_id != run.chapter_id
            or len(request.now_toy_tops) != 3
            or not _trigger_unsupported_fields_are_absent(request)
        ):
            return None
        node = run.nodes.get(request.cur_node.location)
        event = request.cur_node.event
        if (
            request.cur_node.location != run.location
            or node is None
            or event is None
            or node.event_id != event.event_id
            or request.trigger_location != 0
            # `isCompleteAll` only ever reports 1 while standing on the boss
            # with every other node done, so it rides on that trigger alone.
            or request.trigger_all_node not in (0, 1)
            or (
                request.trigger_all_node == 1
                and not is_boss_event(event.event_id)
            )
        ):
            return None
        saved_hp = tuple(
            run.toy_tops[index].hp for index in (1, 2, 3)
        )
        supplied_hp = tuple(top.hp for top in request.now_toy_tops)
        marked = _marked_top(request)
        if event_type(event.event_id) != SELECT_EVENT and any(
            top.buffs for top in request.now_toy_tops
        ):
            # Only a Select confirm names a top; anywhere else a mark is a
            # reward we never offered.
            return None
        rewards: tuple[tuple[int, int], ...] = ()
        include_player_delta = False
        finished_map = False
        if event.event_id == 110019:
            if (
                request.cur_node.location != 10003
                or node.status != 1
                or tuple(node.location_exports) != fixed_exports(110019)
                or len(event.location_exports) != 1
                or event.location_exports[0] not in node.location_exports
                or request.trigger_path != (110000, 110019)
                or request.energy_type != -1
                or request.clear_next_battle_buff != 0
                or supplied_hp != saved_hp
            ):
                return None
            starter_buffs = {
                100095: 4214,
                100080: 4223,
                100090: 4233,
            }
            selected_buff = starter_buffs[event.location_exports[0]]
            run.event_buffs[selected_buff] = (
                run.event_buffs.get(selected_buff, 0) + 1
            )
            node.status = 3
        elif event.event_id == 110005:
            if (
                request.cur_node.location != 10003
                or node.status != 1
                or node.location_exports
                or event.location_exports
                or request.trigger_path != (110000, 110005)
                or request.energy_type != -1
                or request.clear_next_battle_buff != 0
                or supplied_hp != saved_hp
            ):
                return None
            node.status = 3
        elif is_fightable_event(event.event_id):
            # Any battle node, recognised by declared type. The stored exports
            # are whatever the client offered when the node was entered, and
            # how many that is comes from the event's own RandomTime.
            rolled = random_export_count(event.event_id)
            if (
                rolled < 1
                or len(node.location_exports) != rolled
                or len(set(node.location_exports)) != rolled
            ):
                return None
            if node.status == 1:
                if (
                    len(event.location_exports) != rolled
                    or set(event.location_exports)
                    != set(node.location_exports)
                    or request.trigger_path != (event.event_id,)
                    or request.energy_type != 0
                    or request.clear_next_battle_buff != 1
                    or run.pending_battle_reward
                    or any(
                        value < 0 or value > prior
                        for value, prior in zip(supplied_hp, saved_hp)
                    )
                    or not any(supplied_hp)
                ):
                    return None
                for index, value in enumerate(supplied_hp, start=1):
                    run.toy_tops[index].hp = value
                # The boss win is final: doTrigger guards the postbattle
                # chooser with `eventType !== FinalBossEvent`, so no claim
                # follows and leaving the node pending would strand the run.
                boss = is_boss_event(event.event_id)
                node.status = 3 if boss else 2
                run.battle_wins += 1
                run.pending_battle_reward = not boss
                if boss:
                    # The client shows 通关成功 by itself and sends nothing,
                    # so this trigger is the only moment the clear can be
                    # recorded. LevelProcess holds the furthest chapter beaten
                    # at a difficulty, so a replay must never lower it.
                    cleared = profile.roguelike_cleared_chapters
                    furthest = cleared.get(run.chapter_level)
                    if furthest is None or run.chapter_id > furthest:
                        cleared[run.chapter_level] = run.chapter_id
                    # A won run has no other end: `doEndMap` sends GiveUpMap
                    # on a loss only. Leaving the map open after a fully
                    # explored run strands the player on a dead board.
                    finished_map = request.trigger_all_node == 1
                rewards = (
                    (1194340400, 5),
                    (1295005745, 1),
                    (1295005746, 1),
                )
                for item_id, amount in rewards:
                    profile.default_items[item_id] = (
                        profile.default_items.get(item_id, 0) + amount
                    )
                include_player_delta = True
            elif node.status == 2:
                if (
                    len(event.location_exports) != 1
                    or event.location_exports[0]
                    not in POSTBATTLE_EXPORTS
                    or request.trigger_path
                    or request.energy_type != -1
                    or request.clear_next_battle_buff != 0
                    or not run.pending_battle_reward
                ):
                    return None
                selected_export = event.location_exports[0]
                expected_hp = tuple(
                    (
                        (11 * prior + 9) // 10
                        if selected_export == 100069
                        else (6 * prior + 4) // 5
                        if selected_export == 100077
                        else prior
                    )
                    for prior in saved_hp
                )
                if supplied_hp != expected_hp:
                    return None
                for index, value in enumerate(supplied_hp, start=1):
                    run.toy_tops[index].hp = value
                selected_buff = POSTBATTLE_EXPORTS[selected_export]
                run.event_buffs[selected_buff] = (
                    run.event_buffs.get(selected_buff, 0) + 1
                )
                node.status = 3
                run.pending_battle_reward = False
            else:
                return None
        elif event_type(event.event_id) == SELECT_EVENT:
            # The repair station. The client rolls its three choices locally
            # and clears LocationExports on confirm, so the only thing that
            # names the pick is the export item id stamped on the chosen top.
            export = select_export(marked[1]) if marked is not None else None
            top = (
                run.toy_tops.get(marked[0]) if marked is not None else None
            )
            if (
                node.status != 1
                or event.location_exports
                or request.trigger_path != (event.event_id,)
                or request.energy_type != -1
                or request.clear_next_battle_buff != 0
                or export is None
                or top is None
            ):
                return None
            if export.reward_type == RECOVER_HP_REWARD:
                # `setChijiItem` heals before sending, so the confirm carries
                # the repaired value. Only a repair is a percentage of maximum
                # health, so only a repair needs the ceiling; without one it is
                # refused rather than guessed.
                if top.max_hp <= 0:
                    return None
                expected_hp = tuple(
                    repair_hp_effect(
                        prior, top.max_hp, export.export_num
                    )
                    if index == marked[0]
                    else prior
                    for index, prior in enumerate(saved_hp, start=1)
                )
                if supplied_hp != expected_hp:
                    return None
                # dealHp does not clamp; getToyTopMaxHp clamps the client's
                # own copy afterwards, so the stored value is the clamped one.
                top.hp = min(top.max_hp, supplied_hp[marked[0] - 1])
            elif export.reward_type == CHIJI_ITEM_REWARD:
                if supplied_hp != saved_hp:
                    return None
                top.buffs[export.export_item_id] = (
                    top.buffs.get(export.export_item_id, 0)
                    + export.export_num
                )
            else:
                return None
            node.status = 3
        elif event_type(event.event_id) == REWARD_EVENT:
            # A reward chest offers no choice: doTrigger hands the node's
            # whole export list straight back, and every row is an item.
            granted = tuple(
                reward_export(key) for key in event.location_exports
            )
            if (
                node.status != 1
                or len(event.location_exports)
                != len(node.location_exports)
                or set(event.location_exports)
                != set(node.location_exports)
                or request.trigger_path != (event.event_id,)
                or request.energy_type != -1
                or request.clear_next_battle_buff != 0
                or supplied_hp != saved_hp
                or any(
                    row is None or row.reward_type != ITEM_REWARD
                    for row in granted
                )
            ):
                return None
            rewards = tuple(
                (row.export_item_id, row.export_num)
                for row in granted
                if row is not None
            )
            for item_id, amount in rewards:
                profile.default_items[item_id] = (
                    profile.default_items.get(item_id, 0) + amount
                )
            include_player_delta = True
            node.status = 3
        else:
            return None
        if finished_map:
            profile.roguelike_run = None
        store.save(profile)
        frames: list[tuple[int, bytes]] = [
            (5, build_roguelike_info(profile))
        ]
        if include_player_delta:
            frames.append((1, build_roguelike_player_delta(profile)))
        frames.append(
            (
                180,
                build_roguelike_response(
                    code=31,
                    location=run.location,
                    rewards=rewards,
                ),
            )
        )
        return tuple(frames)


@router.websocket("/ws")
async def logic_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    authenticated = False
    profile = None
    try:
        while True:
            try:
                net_id, payload = unpack_frame(
                    await websocket.receive_bytes()
                )
            except ValueError:
                await websocket.close(code=1008)
                return
            known_client_ids = {1111, 131, 163, 166, 181, 182, 183, 184}
            if not authenticated:
                _journal("recv", net_id, net_id in known_client_ids)
                if net_id != 1111:
                    await websocket.close(code=1008)
                    return
                try:
                    token = parse_login_token(payload)
                    claims = verify_logic_token(token)
                except (ValueError, UnicodeDecodeError):
                    await websocket.close(code=1008)
                    return
                if (
                    not isinstance(claims, dict)
                    or type(claims.get("playerid")) is not int
                ):
                    await websocket.close(code=1008)
                    return
                profile = ProfileStore().load("local")
                if claims["playerid"] != profile.player_id:
                    await websocket.close(code=1008)
                    return
                responses = (
                    (1, build_player_data(profile)),
                    (2, b""),
                    (5, build_roguelike_info(profile)),
                    (129, build_sc_login(profile)),
                )
                for response_id, response_payload in responses:
                    await websocket.send_bytes(
                        pack_frame(response_id, response_payload)
                    )
                    _journal("send", response_id, True)
                authenticated = True
                continue

            if net_id == 1111:
                _journal("recv", net_id, True)
                await websocket.close(code=1008)
                return
            if net_id == 163:
                _journal("recv", net_id, True)
                try:
                    if parse_report_status(payload) != 0:
                        raise ValueError("report status must be zero")
                except ValueError:
                    await websocket.close(code=1008)
                    return
                continue
            if net_id == 131:
                _journal("recv", net_id, True)
                if payload:
                    await websocket.close(code=1008)
                    return
                await websocket.send_bytes(pack_frame(132, b""))
                _journal("send", 132, True)
                continue
            if net_id in {181, 182, 184}:
                try:
                    if net_id == 181:
                        roguelike_request = parse_roguelike_enter_map(payload)
                        location = roguelike_request.init_node.location
                        event = roguelike_request.init_node.event
                    elif net_id == 182:
                        roguelike_request = parse_roguelike_enter_node(payload)
                        location = roguelike_request.new_node.location
                        event = roguelike_request.new_node.event
                    else:
                        roguelike_request = parse_roguelike_trigger(payload)
                        location = roguelike_request.cur_node.location
                        event = roguelike_request.cur_node.event
                except ValueError:
                    _journal("recv", net_id, True)
                    await websocket.close(code=1008)
                    return
                _journal(
                    "recv",
                    net_id,
                    True,
                    roguelike_version=roguelike_request.roguelike_version,
                    chapter_id=roguelike_request.chapter_id,
                    location=location,
                    event_id=None if event is None else event.event_id,
                    location_exports=(
                        None if event is None else event.location_exports
                    ),
                    trigger_path=(
                        roguelike_request.trigger_path
                        if net_id == 184
                        else None
                    ),
                    toy_tops=(
                        roguelike_request.now_toy_tops
                        if net_id == 184
                        else None
                    ),
                )
                assert profile is not None
                if net_id == 181:
                    frames = _enter_map_frames(
                        profile.account_id, roguelike_request
                    )
                elif net_id == 182:
                    frames = _enter_node_frames(
                        profile.account_id, roguelike_request
                    )
                else:
                    frames = _trigger_frames(
                        profile.account_id, roguelike_request
                    )
                if frames is None:
                    await websocket.close(code=1008)
                    return
                for response_id, response_payload in frames:
                    await websocket.send_bytes(
                        pack_frame(response_id, response_payload)
                    )
                    _journal("send", response_id, True)
                continue
            if net_id == 183:
                try:
                    misc_request = parse_roguelike_misc_opr(payload)
                except ValueError:
                    _journal("recv", net_id, True)
                    await websocket.close(code=1008)
                    return
                _journal(
                    "recv",
                    net_id,
                    True,
                    roguelike_version=misc_request.roguelike_version,
                    event_id=misc_request.opr_type,
                )
                assert profile is not None
                frames = _battle_over_select_frames(
                    profile.account_id, misc_request
                )
                if frames is None:
                    await websocket.close(code=1008)
                    return
                for response_id, response_payload in frames:
                    await websocket.send_bytes(
                        pack_frame(response_id, response_payload)
                    )
                    _journal("send", response_id, True)
                continue
            if net_id != 166:
                _journal("recv", net_id, False)
                continue
            try:
                chapter_operation = parse_chapter_operation(payload)
            except ValueError:
                _journal("recv", net_id, True)
                await websocket.close(code=1008)
                return
            _journal(
                "recv",
                net_id,
                True,
                chapter_operation.chapter_version,
            )
            if chapter_operation.chapter_key != 10001:
                await websocket.close(code=1008)
                return
            if chapter_operation.operation == 0:
                if (
                    chapter_operation.result is not None
                    or chapter_operation.self_win_num is not None
                    or chapter_operation.use_parts
                ):
                    await websocket.close(code=1008)
                    return
                await websocket.send_bytes(
                    pack_frame(167, build_chapter_opr_ack(0))
                )
                _journal("send", 167, True)
                continue
            if chapter_operation.operation == 3:
                if (
                    chapter_operation.result is not None
                    or chapter_operation.self_win_num is not None
                    or chapter_operation.use_parts
                ):
                    await websocket.close(code=1008)
                    return
                await websocket.send_bytes(
                    pack_frame(167, build_chapter_opr_ack(3))
                )
                _journal("send", 167, True)
                continue
            if (
                chapter_operation.operation != 1
                or chapter_operation.result not in {1, 3, 5, 7}
                or chapter_operation.self_win_num is None
                or chapter_operation.self_win_num < 1
            ):
                await websocket.close(code=1008)
                return
            assert profile is not None
            with profile_transaction():
                profile = ProfileStore().load(profile.account_id)
                achieved_result = (
                    profile.stage_results.get(chapter_operation.chapter_key, 0)
                    | chapter_operation.result
                )
                profile.stage_results[chapter_operation.chapter_key] = achieved_result
                if chapter_operation.chapter_key not in profile.stages_completed:
                    profile.stages_completed.append(chapter_operation.chapter_key)
                ProfileStore().save(profile)
            responses = (
                (
                    1,
                    build_chapter_result_delta(
                        chapter_operation.chapter_key, achieved_result
                    ),
                ),
                (167, build_chapter_opr_ack(1)),
                (140, build_race_end()),
            )
            for response_id, response_payload in responses:
                await websocket.send_bytes(
                    pack_frame(response_id, response_payload)
                )
                _journal("send", response_id, True)
    except WebSocketDisconnect:
        return
