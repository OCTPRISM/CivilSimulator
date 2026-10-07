from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Literal, cast

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from .config import (
    assert_auth_secret_safe,
    assert_cors_safe,
    assert_invite_config_safe,
    effective_invite_only,
    get_settings,
    parse_cors_origins,
)
from .auth import (
    get_current_user,
    get_optional_user,
    require_session_member,
    resolve_acting_player_id,
    user_from_token,
)
from .layer1_foundation.base import LLMServiceError
from .layer1_foundation.rate_limit import rate_limit_play, rate_limit_play_user, rate_limit_register
from .layer2_civilization import list_seeds
from .layer2_civilization.civilization_dashboard import build_dashboard
from .layer2_civilization.civilization_resolver import get_catalog_any, list_all_seeds
from .session import (
    create_session, destroy_session, get_session, heartbeat, join_session,
    kick_player, transfer_host, deliver_remote_fanout,
    npc_reply, page_dict, replay_to_tick, session_dict, sleep_player, step,
    start_background_loop, stop_background_loop, subscribe, unsubscribe,
    wake_player, schedule_event, schedule_character, create_self_task,
    complete_task, skip_to_tick, use_skill,
    run_finance_ticks, apply_finance_shock, ensure_finance, ensure_finance_lab, move_player,
    lab_global_forecast, lab_global_event, lab_city_forecast, lab_city_event,
    lab_corporate_forecast, lab_corporate_event, lab_retail_run,
)
from .layer6_persistence.users import (
    authenticate, create_user, enrich_user_sessions, is_session_member,
    make_token, unlink_session_membership,
)
from .labs import (
    create_or_get_lab, get_lab, get_lab_meta, list_labs, lab_snapshot, rebind_civilization,
    lab_advance_finance, lab_apply_shock,
    lab_global_forecast as lab_ws_global_forecast,
    lab_global_event as lab_ws_global_event,
    lab_city_forecast as lab_ws_city_forecast,
    lab_city_event as lab_ws_city_event,
    lab_corporate_forecast as lab_ws_corporate_forecast,
    lab_corporate_event as lab_ws_corporate_event,
    lab_retail_run as lab_ws_retail_run,
    lab_opinion_simulate, lab_opinion_intervene, lab_opinion_node,
    lab_military_simulate, lab_military_configure,
    lab_policy_simulate, lab_weather_simulate, lab_environment_simulate,
    lab_population_simulate, lab_population_shock, lab_population_policy, lab_population_cognition,
    lab_upload_dataset, lab_add_manual_events, lab_run_report, lab_finance_simulate,
)
from .layer6_persistence.custom_civilizations import (
    create_custom_civilization, list_custom_civilizations, get_custom_civilization,
    update_custom_civilization, delete_custom_civilization,
)
from .generator import hunyuan_client
from .generator.outfits import get_outfit, list_civilizations as list_outfit_civilizations
from .generator.service import (
    create_character_job,
    create_map_job,
    create_model_job_from_image,
    create_model_job_from_text,
    get_character_glb_path,
    get_character_outfits,
    get_map_paths,
    get_model_glb_path,
)
from .generator import jobs as gen_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # R0-3 / R0-4 / R1-5 startup gates.
    s = get_settings()
    assert_auth_secret_safe(s)
    assert_cors_safe(s)
    assert_invite_config_safe(s)
    start_background_loop()
    # MP-4: optional Redis room bus — never blocks cold start.
    from . import room_bus
    await room_bus.start(handler=deliver_remote_fanout)
    yield
    # B-1: flush restorable snapshots before process exit.
    try:
        from .session_persist import flush_all_sessions
        flush_all_sessions()
    except Exception:
        pass
    try:
        await room_bus.stop()
    except Exception:
        pass
    stop_background_loop()


app = FastAPI(title="Civilization Simulator", version="0.4.0", lifespan=lifespan)

_CORS_ORIGINS = parse_cors_origins(get_settings().cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=_CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- REST ----------
@app.get("/api/health")
async def api_health():
    """Liveness + room-bus mode (MP-4). Always 200 when the process is up."""
    from . import room_bus
    return {
        "ok": True,
        "version": "0.4.0",
        "room_bus": room_bus.status(),
    }


@app.get("/api/seeds")
async def api_seeds(user=Depends(get_optional_user)):
    if user:
        return {"seeds": list_all_seeds(user.id)}
    return {"seeds": list_seeds()}


@app.get("/api/seeds/{seed_key}/characters")
async def api_seed_characters(seed_key: str, user=Depends(get_optional_user)):
    try:
        return get_catalog_any(seed_key, user.id if user else None)
    except FileNotFoundError:
        raise HTTPException(404, "seed not found")


@app.get("/api/seeds/{seed_key}/dashboard")
async def api_seed_dashboard(seed_key: str, user=Depends(get_optional_user)):
    try:
        return {"dashboard": build_dashboard(seed_key, user.id if user else None)}
    except FileNotFoundError:
        raise HTTPException(404, "seed not found")


class CustomCivilizationReq(BaseModel):
    name: str = "未命名文明"
    genre: str = "custom"
    premise: str = ""
    class_structure: dict[str, float] | None = None
    age_structure: dict[str, float] | None = None
    operating_logic: str
    government_form: str = ""
    professions: list[dict] | None = None
    roles: list[dict] | None = None
    historical_events: list[dict] | None = None
    current_stage: str = ""
    rules: list[str] | None = None
    locations: list[dict] | None = None
    factions: list[dict] | None = None
    opening_scene: str = ""


@app.get("/api/civilizations/custom")
async def api_list_custom_civilizations(user=Depends(get_current_user)):
    return {"civilizations": list_custom_civilizations(user.id)}


@app.post("/api/civilizations/custom")
async def api_create_custom_civilization(req: CustomCivilizationReq, user=Depends(get_current_user)):
    try:
        row = create_custom_civilization(user.id, req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    cfg = row["config"]
    return {
        "civilization": {
            "id": row["id"],
            "key": row["key"],
            "name": row["name"],
            "genre": cfg.get("genre") or "custom",
            "premise": cfg.get("premise") or cfg.get("current_stage") or cfg.get("operating_logic", "")[:120],
            "is_custom": True,
        }
    }


@app.get("/api/civilizations/custom/{civ_id}")
async def api_get_custom_civilization(civ_id: str, user=Depends(get_current_user)):
    row = get_custom_civilization(civ_id, user.id)
    if not row:
        raise HTTPException(404, "civilization not found")
    return {"civilization": row}


@app.put("/api/civilizations/custom/{civ_id}")
async def api_update_custom_civilization(
    civ_id: str, req: CustomCivilizationReq, user=Depends(get_current_user),
):
    try:
        row = update_custom_civilization(civ_id, user.id, req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not row:
        raise HTTPException(404, "civilization not found")
    cfg = row["config"]
    return {
        "civilization": {
            "id": row["id"],
            "key": row["key"],
            "name": row["name"],
            "genre": cfg.get("genre") or "custom",
            "premise": cfg.get("premise") or cfg.get("current_stage") or cfg.get("operating_logic", "")[:120],
            "is_custom": True,
            "config": cfg,
        }
    }


@app.delete("/api/civilizations/custom/{civ_id}")
async def api_delete_custom_civilization(civ_id: str, user=Depends(get_current_user)):
    if not delete_custom_civilization(civ_id, user.id):
        raise HTTPException(404, "civilization not found")
    return {"ok": True}


class RegisterReq(BaseModel):
    username: str
    password: str
    display_name: str = ""
    invite_code: str | None = None


class LoginReq(BaseModel):
    username: str
    password: str


@app.get("/api/auth/config")
async def api_auth_config():
    """Public auth policy for the login UI (R1-5) — no secrets."""
    s = get_settings()
    return {
        "invite_only": effective_invite_only(s),
        "min_password_length": int(s.min_password_length),
        "llm_provider": s.llm_provider,
    }


@app.post("/api/auth/register")
async def api_register(req: RegisterReq, _rl=Depends(rate_limit_register)):
    import hmac as _hmac

    s = get_settings()
    if effective_invite_only(s):
        expected = (s.invite_code or "").strip()
        got = (req.invite_code or "").strip()
        # Length guard: hmac.compare_digest raises on unequal lengths.
        if (
            not expected
            or len(got) != len(expected)
            or not _hmac.compare_digest(got, expected)
        ):
            raise HTTPException(403, "当前为邀测模式，需要有效注册码")
    try:
        user = create_user(req.username, req.password, req.display_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    token = make_token(user.id)
    return {"token": token, "user": user.as_public()}


@app.post("/api/auth/login")
async def api_login(req: LoginReq):
    user = authenticate(req.username, req.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = make_token(user.id)
    return {"token": token, "user": user.as_public()}


@app.get("/api/auth/me")
async def api_me(user=Depends(get_current_user)):
    return {"user": user.as_public(), "sessions": enrich_user_sessions(user.id)}


@app.get("/api/sessions")
async def api_list_sessions(user=Depends(get_current_user)):
    """R1-1: authenticated membership list only (no public room dump)."""
    return {"sessions": enrich_user_sessions(user.id)}


class CreateSessionReq(BaseModel):
    seed_key: str
    description: str = ""
    category_key: str | None = None
    variant_key: str | None = None
    skin: str | None = None
    max_players: int = Field(default=8, ge=2, le=16)


@app.post("/api/sessions")
async def api_create_session(req: CreateSessionReq, user=Depends(get_current_user)):
    try:
        sess = await create_session(
            req.seed_key,
            req.description,
            category_key=req.category_key,
            variant_key=req.variant_key,
            skin=req.skin,
            user_id=user.id,
            max_players=req.max_players,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "seed not found")
    except LLMServiceError as e:
        raise HTTPException(503, e.message) from e
    except Exception as e:
        raise HTTPException(500, f"创建世界失败：{e}") from e
    try:
        page = await step(sess, player_input=None)
    except LLMServiceError as e:
        # R1-3: do not leave a half-open room after LLM failure on opening page.
        destroy_session(sess.id)
        unlink_session_membership(sess.id, user.id)
        raise HTTPException(503, e.message) from e
    except Exception as e:
        # Session already exists — enter with a local opening page instead of 500.
        from .layer4_narrative.scene import Beat, Page
        from .layer4_narrative.choices import choices_for_scene
        player = sess.society.get(sess.primary_player_id) if sess.primary_player_id else None
        if not player:
            destroy_session(sess.id)
            unlink_session_membership(sess.id, user.id)
            raise HTTPException(500, f"开场叙事失败且无主角：{e}") from e
        scene = sess.director.pick_scene(sess.world, sess.society, player)
        page = Page(
            page_no=max(1, sess.director.page_no + 1),
            chapter=str(sess.director.chapter),
            scene=scene,
            beats=[
                Beat(
                    kind="system",
                    speaker=None,
                    content=f"世界已就绪（开场叙事暂缓：{type(e).__name__}）。可继续行动。",
                ),
                Beat(
                    kind="narration",
                    speaker=None,
                    content=f"{scene.location_name}的风声先于人声而来。{player.name}站定，打量四周。",
                ),
            ],
            choices=choices_for_scene(
                location_name=scene.location_name, genre=sess.world.genre,
            ),
        )
        sess.director.page_no = page.page_no
        sess.pages.append(page)
    try:
        from .session_persist import force_save_snapshot
        force_save_snapshot(sess)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to force-save snapshot on create for %s", sess.id,
        )
    return {"session": session_dict(sess), "page": page_dict(page)}


@app.get("/api/sessions/{sid}/invite")
async def api_invite_preview(sid: str, user=Depends(get_current_user)):
    """Authenticated invite preview — no membership required (R0 join UX)."""
    sess = get_session(sid)
    if not sess:
        # B-2: allow preview of restorable rooms for members / invitees after restart.
        from .session_persist import latest_snapshot_meta
        meta = latest_snapshot_meta(sid)
        if not meta or not meta.get("compatible"):
            raise HTTPException(404, "session not found")
        return {
            "session_id": sid,
            "world_name": meta.get("world_name") or sid,
            "genre": meta.get("genre") or "",
            "players": len(meta.get("player_ids") or []),
            "max_players": meta.get("max_players"),
            "already_member": is_session_member(sid, user.id),
            "live": False,
            "restorable": True,
        }
    return {
        "session_id": sid,
        "world_name": sess.world.name,
        "genre": sess.world.genre,
        "players": len(sess.player_ids),
        "max_players": int(getattr(sess, "max_players", 8) or 8),
        "already_member": is_session_member(sid, user.id),
        "live": True,
        "restorable": False,
    }


@app.post("/api/sessions/{sid}/restore")
async def api_restore_session(sid: str, user=Depends(get_current_user)):
    """B-2: hydrate a room from the latest Scheme B snapshot into this process."""
    if not is_session_member(sid, user.id):
        raise HTTPException(403, "你不是该世界的成员")
    from .session_persist import RestoreError, restore_session
    try:
        sess = restore_session(sid)
    except RestoreError as e:
        raise HTTPException(409, e.message) from e
    viewer = resolve_acting_player_id(sid, user, sess, None)
    return {"session": session_dict(sess, viewer_id=viewer), "restored": True}


class KickReq(BaseModel):
    player_id: str


@app.post("/api/sessions/{sid}/kick")
async def api_kick_player(
    sid: str, req: KickReq, access=Depends(require_session_member),
):
    """MP-2: host kicks a player out of the live room."""
    sess, user = access
    from .layer6_persistence.users import get_member_player_id
    viewer = get_member_player_id(sid, user.id)
    try:
        payload = kick_player(
            sess,
            host_user_id=user.id,
            target_player_id=req.player_id,
            viewer_id=viewer,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return payload


class TransferHostReq(BaseModel):
    to_user_id: str


@app.post("/api/sessions/{sid}/transfer-host")
async def api_transfer_host(
    sid: str, req: TransferHostReq, access=Depends(require_session_member),
):
    """MP-2: host transfers ownership to another member."""
    sess, user = access
    from .layer6_persistence.users import get_member_player_id
    viewer = get_member_player_id(sid, user.id)
    try:
        payload = transfer_host(
            sess,
            host_user_id=user.id,
            to_user_id=req.to_user_id,
            viewer_id=viewer,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return payload


@app.get("/api/sessions/{sid}")
async def api_get_session(
    sid: str,
    player_id: str | None = None,
    access=Depends(require_session_member),
):
    sess, user = access
    viewer = resolve_acting_player_id(sid, user, sess, player_id)
    return {"session": session_dict(sess, viewer_id=viewer)}


class JoinReq(BaseModel):
    description: str = "一位新来的旅人"
    category_key: str | None = None
    variant_key: str | None = None
    skin: str | None = None


@app.post("/api/sessions/{sid}/join")
async def api_join_session(
    sid: str, req: JoinReq, user=Depends(get_current_user), _rl=Depends(rate_limit_play),
):
    try:
        # Catalog join reuses create-path variants when provided.
        description = req.description.strip()
        if req.category_key and req.variant_key:
            from .layer2_civilization.civilization_resolver import resolve_variant_any
            from .session_persist import RestoreError, restore_session
            sess0 = get_session(sid)
            if not sess0:
                try:
                    sess0 = restore_session(sid)
                except RestoreError as e:
                    raise KeyError(e.message) from e
            variant = resolve_variant_any(
                sess0.seed_key or "ancient",
                req.category_key,
                req.variant_key,
                user_id=user.id,
            )
            if not variant:
                raise HTTPException(400, "角色形象不存在")
            description = (
                f"{variant.get('name') or '旅人'}。"
                f"{variant.get('persona') or description}"
            )
        sess, player = await join_session(
            sid, description or "一位新来的旅人", user_id=user.id,
        )
    except KeyError:
        raise HTTPException(404, "session not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LLMServiceError as e:
        raise HTTPException(503, e.message) from e
    except Exception as e:
        raise HTTPException(500, f"加入失败：{e}") from e
    return {
        "session": session_dict(sess, viewer_id=player.id),
        "player_id": player.id,
    }


class StepReq(BaseModel):
    input: str | None = None
    player_id: str | None = None


@app.post("/api/sessions/{sid}/step")
async def api_step(
    sid: str, req: StepReq, access=Depends(require_session_member), _rl=Depends(rate_limit_play),
):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    try:
        page = await step(sess, player_id=pid, player_input=req.input)
    except LLMServiceError as e:
        raise HTTPException(503, e.message) from e
    return {
        "page": page_dict(page),
        "stats": sess.director.stats.snapshot(),
        "session": session_dict(sess, viewer_id=pid),
    }


class UseSkillReq(BaseModel):
    skill_id: str
    player_id: str | None = None


@app.post("/api/sessions/{sid}/use-skill")
async def api_use_skill(sid: str, req: UseSkillReq, access=Depends(require_session_member)):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    try:
        page = await use_skill(sess, skill_id=req.skill_id, player_id=pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LLMServiceError as e:
        raise HTTPException(503, e.message) from e
    return {
        "page": page_dict(page),
        "stats": sess.director.stats.snapshot(),
        "session": session_dict(sess, viewer_id=pid),
    }


@app.get("/api/sessions/{sid}/replay")
async def api_replay(
    sid: str,
    to_tick: int = 999_999,
    access=Depends(require_session_member),
):
    _sess, _user = access
    return {"session": replay_to_tick(sid, to_tick=to_tick)}


# ---------- presence / dormancy ----------
class PresenceReq(BaseModel):
    player_id: str | None = None
    reason: str = "offline"


@app.post("/api/sessions/{sid}/heartbeat")
async def api_heartbeat(sid: str, req: PresenceReq, access=Depends(require_session_member)):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    player = await heartbeat(sess, player_id=pid)
    return {
        "player_id": player.id,
        "presence": player.presence.value,
        "tick": sess.world.clock.tick,
    }


@app.post("/api/sessions/{sid}/sleep")
async def api_sleep(sid: str, req: PresenceReq, access=Depends(require_session_member)):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    player = await sleep_player(sess, player_id=pid, reason=req.reason)
    return {
        "player_id": player.id,
        "presence": player.presence.value,
        "offline_mode": player.offline_mode,
        "offline_rationale": player.offline_rationale,
        "dormant_since_tick": player.dormant_since_tick,
        "session": session_dict(sess, viewer_id=player.id),
    }


@app.post("/api/sessions/{sid}/wake")
async def api_wake(sid: str, req: PresenceReq, access=Depends(require_session_member)):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    return await wake_player(sess, player_id=pid)


# ---------- NPC interaction ----------
@app.get("/api/sessions/{sid}/clock")
async def api_clock(sid: str, access=Depends(require_session_member)):
    sess, _user = access
    c = sess.world.clock
    return {"tick": c.tick, "hour": c.hour_of_day, "day": c.day,
            "era": c.era, "label": c.label()}


@app.get("/api/sessions/{sid}/npcs")
async def api_list_npcs(
    sid: str,
    location_id: str | None = None,
    access=Depends(require_session_member),
):
    sess, _user = access
    npcs = sess.society.npcs()
    if location_id:
        npcs = [a for a in npcs if a.location_id == location_id]
    loc_name_by_id = {loc.id: loc.name for loc in sess.world.locations.values()}
    return {"npcs": [
        {
            "id": a.id, "name": a.name, "avatar": getattr(a, "avatar", ""),
            "persona": a.persona, "goals": a.goals, "traits": a.traits,
            "location_id": a.location_id,
            "location_name": loc_name_by_id.get(a.location_id, ""),
            "profession": getattr(a, "profession", ""),
            "current_activity": getattr(a, "current_activity", ""),
            "schedule": list(getattr(a, "schedule", [])),
            "economy": dict(getattr(a, "economy", {})),
            "savings": getattr(a, "savings", 0.0),
            "today_income": getattr(a, "today_income", 0.0),
            "today_customers": getattr(a, "today_customers", 0),
            "last_meal_tier": getattr(a, "last_meal_tier", ""),
            "presence": getattr(getattr(a, "presence", None), "value", "active"),
        } for a in npcs
    ]}


class TalkReq(BaseModel):
    npc_id: str
    text: str
    player_id: str | None = None


@app.post("/api/sessions/{sid}/talk")
async def api_talk(
    sid: str, req: TalkReq, access=Depends(require_session_member), _rl=Depends(rate_limit_play),
):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    try:
        result = await npc_reply(sess, npc_id=req.npc_id, text=req.text,
                                 player_id=pid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


# ---------- custom injections (events / characters at tick) ----------
class InjectEventReq(BaseModel):
    tick: int
    summary: str
    importance: float = 0.85
    location_id: str | None = None


class InjectCharacterReq(BaseModel):
    tick: int
    name: str
    persona: str
    profession: str = ""
    location_id: str | None = None
    traits: list[str] = []
    agent_kind: str = "npc"  # npc | animal


@app.get("/api/sessions/{sid}/injections")
async def api_list_injections(sid: str, access=Depends(require_session_member)):
    sess, _user = access
    return {"injections": sess.injections.snapshot(), "tick": sess.world.clock.tick}


@app.post("/api/sessions/{sid}/inject/event")
async def api_inject_event(sid: str, req: InjectEventReq, access=Depends(require_session_member)):
    sess, _user = access
    inj = await schedule_event(
        sess, tick=req.tick, summary=req.summary,
        importance=req.importance, location_id=req.location_id,
    )
    return {"injection": inj, "session": session_dict(sess)}


@app.post("/api/sessions/{sid}/inject/character")
async def api_inject_character(
    sid: str, req: InjectCharacterReq, access=Depends(require_session_member),
):
    sess, _user = access
    inj = await schedule_character(
        sess, tick=req.tick, name=req.name, persona=req.persona,
        profession=req.profession, location_id=req.location_id,
        traits=req.traits, agent_kind=req.agent_kind,
    )
    return {"injection": inj, "session": session_dict(sess)}


class SkipTickReq(BaseModel):
    target_tick: int


@app.post("/api/sessions/{sid}/skip-to-tick")
async def api_skip_to_tick(sid: str, req: SkipTickReq, access=Depends(require_session_member)):
    sess, _user = access
    return await skip_to_tick(sess, req.target_tick)


# ---------- finance validation MVP ----------
@app.get("/api/sessions/{sid}/finance")
async def api_finance(sid: str, format: str = "json", access=Depends(require_session_member)):
    sess, _user = access
    fin = ensure_finance(sess)
    if format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            fin.export_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="finance_{sid}.csv"'},
        )
    return {"finance": fin.snapshot(), "tick": sess.world.clock.tick}


class FinanceShockReq(BaseModel):
    kind: str = "demand"          # supply | demand | price
    good_id: str = "*"
    magnitude: float = 0.35
    duration: int = 12
    note: str = ""


@app.post("/api/sessions/{sid}/finance/shock")
async def api_finance_shock(sid: str, req: FinanceShockReq, access=Depends(require_session_member)):
    sess, _user = access
    try:
        return await apply_finance_shock(
            sess,
            kind=req.kind,
            good_id=req.good_id,
            magnitude=req.magnitude,
            duration=req.duration,
            note=req.note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


class FinanceAdvanceReq(BaseModel):
    steps: int = 24


@app.post("/api/sessions/{sid}/finance/advance")
async def api_finance_advance(
    sid: str, req: FinanceAdvanceReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await run_finance_ticks(sess, req.steps)


@app.get("/api/sessions/{sid}/finance/lab")
async def api_finance_lab(sid: str, access=Depends(require_session_member)):
    sess, _user = access
    lab = ensure_finance_lab(sess)
    return {"finance_lab": lab.snapshot()}


class LabEventReq(BaseModel):
    at_step: int = 12
    title: str
    kind: str = "custom"
    magnitude: float = 0.2
    note: str = ""


class LabForecastReq(BaseModel):
    horizon: int = 24
    company_name: str | None = None
    sector: str | None = None
    city_key: str | None = None
    company_key: str | None = None


class LabRetailReq(BaseModel):
    risk: str = "balanced"       # conservative | balanced | aggressive
    horizon: str = "auto"        # auto | short | long
    capital: float | None = None


@app.post("/api/sessions/{sid}/finance/lab/global/forecast")
async def api_lab_global_forecast(
    sid: str, req: LabForecastReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_global_forecast(sess, horizon=req.horizon)


@app.post("/api/sessions/{sid}/finance/lab/global/event")
async def api_lab_global_event(
    sid: str, req: LabEventReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_global_event(
        sess, at_step=req.at_step, title=req.title,
        kind=req.kind, magnitude=req.magnitude, note=req.note,
    )


@app.post("/api/sessions/{sid}/finance/lab/city/forecast")
async def api_lab_city_forecast(
    sid: str, req: LabForecastReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_city_forecast(sess, horizon=req.horizon, city_key=req.city_key)


@app.post("/api/sessions/{sid}/finance/lab/city/event")
async def api_lab_city_event(
    sid: str, req: LabEventReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_city_event(
        sess, at_step=req.at_step, title=req.title,
        kind=req.kind, magnitude=req.magnitude, note=req.note,
    )


@app.post("/api/sessions/{sid}/finance/lab/corporate/forecast")
async def api_lab_corporate_forecast(
    sid: str, req: LabForecastReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_corporate_forecast(
        sess, horizon=req.horizon,
        company_name=req.company_name, sector=req.sector,
        company_key=req.company_key,
    )


@app.post("/api/sessions/{sid}/finance/lab/corporate/event")
async def api_lab_corporate_event(
    sid: str, req: LabEventReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_corporate_event(
        sess, at_step=req.at_step, title=req.title,
        kind=req.kind, magnitude=req.magnitude, note=req.note,
    )


@app.post("/api/sessions/{sid}/finance/lab/retail/run")
async def api_lab_retail_run(
    sid: str, req: LabRetailReq, access=Depends(require_session_member),
):
    sess, _user = access
    return await lab_retail_run(
        sess, risk=req.risk, horizon=req.horizon, capital=req.capital,
    )


# ---------- standalone experiment labs ----------
class OpenLabReq(BaseModel):
    civilization_key: str = "modern"
    genre: str = "modern"  # legacy compat


@app.get("/api/labs")
async def api_list_labs():
    return {"labs": list_labs()}


@app.post("/api/labs/{lab_key}/open")
async def api_open_lab(lab_key: str, req: OpenLabReq, user=Depends(get_current_user)):
    meta = get_lab_meta(lab_key)
    if not meta:
        raise HTTPException(404, "lab not found")
    civ_key = req.civilization_key or req.genre or "modern"
    try:
        ws = create_or_get_lab(user_id=user.id, lab_key=lab_key, civilization_key=civ_key)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404, "lab or civilization not found")
    return lab_snapshot(ws)


class RebindLabReq(BaseModel):
    civilization_key: str


@app.post("/api/labs/workspace/{lab_id}/rebind")
async def api_rebind_lab(lab_id: str, req: RebindLabReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        rebind_civilization(ws, req.civilization_key)
    except FileNotFoundError:
        raise HTTPException(404, "civilization not found")
    return lab_snapshot(ws)


@app.get("/api/labs/workspace/{lab_id}")
async def api_get_lab_workspace(lab_id: str, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    return lab_snapshot(ws)


@app.post("/api/labs/workspace/{lab_id}/finance/advance")
async def api_lab_ws_advance(lab_id: str, req: FinanceAdvanceReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_advance_finance(ws, steps=req.steps)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/shock")
async def api_lab_ws_shock(lab_id: str, req: FinanceShockReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_apply_shock(
            ws, kind=req.kind, good_id=req.good_id,
            magnitude=req.magnitude, duration=req.duration, note=req.note,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/global/forecast")
async def api_lab_ws_global_forecast(lab_id: str, req: LabForecastReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_global_forecast(ws, horizon=req.horizon)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/global/event")
async def api_lab_ws_global_event(lab_id: str, req: LabEventReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_global_event(
            ws, at_step=req.at_step, title=req.title,
            kind=req.kind, magnitude=req.magnitude, note=req.note,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/city/forecast")
async def api_lab_ws_city_forecast(lab_id: str, req: LabForecastReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_city_forecast(ws, horizon=req.horizon, city_key=req.city_key)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/city/event")
async def api_lab_ws_city_event(lab_id: str, req: LabEventReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_city_event(
            ws, at_step=req.at_step, title=req.title,
            kind=req.kind, magnitude=req.magnitude, note=req.note,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/corporate/forecast")
async def api_lab_ws_corporate_forecast(lab_id: str, req: LabForecastReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_corporate_forecast(
            ws, horizon=req.horizon,
            company_name=req.company_name, sector=req.sector,
            company_key=req.company_key,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/corporate/event")
async def api_lab_ws_corporate_event(lab_id: str, req: LabEventReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_corporate_event(
            ws, at_step=req.at_step, title=req.title,
            kind=req.kind, magnitude=req.magnitude, note=req.note,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/finance/lab/retail/run")
async def api_lab_ws_retail_run(lab_id: str, req: LabRetailReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_ws_retail_run(
            ws, risk=req.risk, horizon=req.horizon, capital=req.capital,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


class OpinionSimReq(BaseModel):
    steps: int = 24
    topic: str = ""


class OpinionInterveneReq(BaseModel):
    key: str
    note: str = ""


class OpinionNodeReq(BaseModel):
    at_step: int
    title: str
    kind: str = "custom"
    magnitude: float = 0.2


@app.post("/api/labs/workspace/{lab_id}/opinion/simulate")
async def api_lab_opinion_simulate(lab_id: str, req: OpinionSimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_opinion_simulate(ws, steps=req.steps, topic=req.topic)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/opinion/intervene")
async def api_lab_opinion_intervene(lab_id: str, req: OpinionInterveneReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_opinion_intervene(ws, req.key, note=req.note)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/opinion/node")
async def api_lab_opinion_node(lab_id: str, req: OpinionNodeReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_opinion_node(
            ws, at_step=req.at_step, title=req.title, kind=req.kind, magnitude=req.magnitude,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


class MilitarySimReq(BaseModel):
    steps: int = 12
    scenario_key: str | None = None
    battlefield_key: str | None = None


class MilitaryConfigReq(BaseModel):
    scenario_key: str = ""
    battlefield_key: str = "rural"


@app.post("/api/labs/workspace/{lab_id}/military/configure")
async def api_lab_military_configure(lab_id: str, req: MilitaryConfigReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_military_configure(
            ws, scenario_key=req.scenario_key, battlefield_key=req.battlefield_key,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/military/simulate")
async def api_lab_military_simulate(lab_id: str, req: MilitarySimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_military_simulate(
            ws,
            scenario_key=req.scenario_key,
            battlefield_key=req.battlefield_key,
            steps=req.steps,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


class PolicySimReq(BaseModel):
    steps: int = 24
    agency_key: str | None = None
    instrument_key: str | None = None


class WeatherSimReq(BaseModel):
    steps: int = 24
    role_key: str | None = None
    pattern_key: str | None = None


class EnvironmentSimReq(BaseModel):
    steps: int = 36
    region_key: str | None = None
    measure_key: str | None = None
    emission_intensity: float | None = None
    enterprise_name: str | None = None


@app.post("/api/labs/workspace/{lab_id}/policy/simulate")
async def api_lab_policy_simulate(lab_id: str, req: PolicySimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    if ws.lab_key != "policy":
        raise HTTPException(400, "not a policy workspace")
    try:
        return await lab_policy_simulate(
            ws, agency_key=req.agency_key, instrument_key=req.instrument_key, steps=req.steps,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/weather/simulate")
async def api_lab_weather_simulate(lab_id: str, req: WeatherSimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    if ws.lab_key != "weather":
        raise HTTPException(400, "not a weather workspace")
    try:
        return await lab_weather_simulate(
            ws, role_key=req.role_key, pattern_key=req.pattern_key, steps=req.steps,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/environment/simulate")
async def api_lab_environment_simulate(lab_id: str, req: EnvironmentSimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    if ws.lab_key != "environment":
        raise HTTPException(400, "not an environment workspace")
    try:
        return await lab_environment_simulate(
            ws,
            region_key=req.region_key,
            measure_key=req.measure_key,
            emission_intensity=req.emission_intensity,
            enterprise_name=req.enterprise_name,
            steps=req.steps,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


class PopulationSimReq(BaseModel):
    years: int = 10
    scope: str = "global"
    region_key: str | None = None
    city_key: str | None = None


@app.post("/api/labs/workspace/{lab_id}/population/simulate")
async def api_lab_population_simulate(lab_id: str, req: PopulationSimReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    if ws.lab_key != "population":
        raise HTTPException(400, "not a population workspace")
    try:
        return await lab_population_simulate(
            ws,
            years=req.years,
            scope=req.scope,
            region_key=req.region_key,
            city_key=req.city_key,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


class PopulationShockReq(BaseModel):
    kind: str
    magnitude: float = 1.0
    note: str = ""


class PopulationPolicyReq(BaseModel):
    kind: str
    magnitude: float = 1.0


@app.post("/api/labs/workspace/{lab_id}/population/shock")
async def api_lab_population_shock(lab_id: str, req: PopulationShockReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_population_shock(ws, req.kind, magnitude=req.magnitude, note=req.note)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/population/policy")
async def api_lab_population_policy(lab_id: str, req: PopulationPolicyReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_population_policy(ws, req.kind, magnitude=req.magnitude)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/population/cognition")
async def api_lab_population_cognition(lab_id: str, req: PopulationPolicyReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_population_cognition(ws, req.kind, magnitude=req.magnitude)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


class ManualEventsReq(BaseModel):
    events: list[dict]
    use_llm_ner: bool = True


class LabReportReq(BaseModel):
    horizon: int = 24
    mode: str = "auto"  # auto | global | city


class FinanceSimulateReq(BaseModel):
    mode: str = "global"
    horizon: int = 24
    city_key: str | None = None
    company_key: str | None = None
    company_name: str | None = None
    sector: str | None = None
    risk: str = "balanced"
    retail_horizon: str = "auto"
    capital: float | None = None
    market_steps: int | None = None
    skip_llm: bool = False


@app.post("/api/labs/workspace/{lab_id}/finance/simulate")
async def api_lab_finance_simulate(lab_id: str, req: FinanceSimulateReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    if ws.lab_key != "finance":
        raise HTTPException(400, "not a finance workspace")
    try:
        return await lab_finance_simulate(
            ws, mode=req.mode, horizon=req.horizon,
            city_key=req.city_key, company_key=req.company_key,
            company_name=req.company_name, sector=req.sector,
            risk=req.risk, retail_horizon=req.retail_horizon,
            capital=req.capital, market_steps=req.market_steps,
            skip_llm=req.skip_llm,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/datasets/upload")
async def api_lab_upload_dataset(
    lab_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(400, "file too large (max 8MB)")
    try:
        return await lab_upload_dataset(ws, file.filename or "upload.dat", content)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/events/manual")
async def api_lab_manual_events(lab_id: str, req: ManualEventsReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_add_manual_events(ws, req.events, use_llm_ner=req.use_llm_ner)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/labs/workspace/{lab_id}/report/run")
async def api_lab_run_report(lab_id: str, req: LabReportReq, user=Depends(get_current_user)):
    ws = get_lab(lab_id)
    if not ws or ws.user_id != user.id:
        raise HTTPException(404, "lab workspace not found")
    try:
        return await lab_run_report(ws, horizon=req.horizon, mode=req.mode)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))


# ---------- tasks ----------
class SelfTaskReq(BaseModel):
    title: str
    description: str = ""
    rewards: dict | None = None
    player_id: str | None = None


class CompleteTaskReq(BaseModel):
    player_id: str | None = None


@app.get("/api/sessions/{sid}/tasks")
async def api_list_tasks(
    sid: str,
    player_id: str | None = None,
    access=Depends(require_session_member),
):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, player_id) or sess.primary_player_id
    if not pid:
        raise HTTPException(400, "no player")
    return {"tasks": sess.tasks.snapshot(pid), "tick": sess.world.clock.tick}


@app.post("/api/sessions/{sid}/tasks/self")
async def api_create_self_task(
    sid: str, req: SelfTaskReq, access=Depends(require_session_member),
):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    task = await create_self_task(
        sess, player_id=pid, title=req.title,
        description=req.description, rewards=req.rewards,
    )
    return {"task": task, "session": session_dict(sess)}


@app.post("/api/sessions/{sid}/tasks/{task_id}/complete")
async def api_complete_task(
    sid: str, task_id: str, req: CompleteTaskReq, access=Depends(require_session_member),
):
    sess, user = access
    pid = resolve_acting_player_id(sid, user, sess, req.player_id)
    result = await complete_task(sess, player_id=pid, task_id=task_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return {**result, "session": session_dict(sess)}


# ---------- TTS / multimodal media (M3) ----------
@app.get("/api/tts/info")
async def api_tts_info():
    return {
        "backend_tts": False,
        "use_browser_speech_synthesis": True,
        "bgm": "procedural_webaudio",
        "scene_art": "pillow_atmosphere",
    }


@app.get("/api/media/scene-art")
async def api_scene_art(
    genre: str = "ancient",
    location: str = "",
    summary: str = "",
    hour: float = 12.0,
    tension: float = 0.3,
):
    """Cinematic atmosphere plate for Play dialogue (cached PNG)."""
    try:
        from .layer1_foundation.scene_art import generate_scene_plate
        path = generate_scene_plate(
            genre=genre or "ancient",
            location_name=location or "",
            summary=summary or "",
            hour=float(hour),
            tension=float(tension),
        )
    except Exception as e:
        raise HTTPException(500, f"scene art failed: {e}") from e
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------- WebSocket (room-based) ----------
async def _ws_reject(ws: WebSocket, message: str, code: int = 1008) -> None:
    try:
        await ws.send_json({"type": "error", "message": message})
    except Exception:
        pass
    try:
        await ws.close(code=code)
    except Exception:
        pass


@app.websocket("/ws/sessions/{sid}")
async def ws_session(
    ws: WebSocket,
    sid: str,
    player_id: str | None = None,
    token: str | None = None,
):
    """Room WS — R0-2: require token + membership **before** snapshot / restore."""
    await ws.accept()
    from .session_persist import RestoreError, restore_session

    auth_token = (token or "").strip() or None
    pending_hello: dict | None = None

    # Allow first-frame hello to carry token when query omits it.
    if not auth_token:
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=8.0)
        except (asyncio.TimeoutError, WebSocketDisconnect):
            await _ws_reject(ws, "未登录或登录已过期")
            return
        try:
            pending_hello = json.loads(raw)
        except json.JSONDecodeError:
            await _ws_reject(ws, "未登录或登录已过期")
            return
        if pending_hello.get("type") != "hello":
            await _ws_reject(ws, "未登录或登录已过期")
            return
        auth_token = (pending_hello.get("token") or "").strip() or None
        if not auth_token:
            await _ws_reject(ws, "未登录或登录已过期")
            return

    user = user_from_token(auth_token)
    if not user:
        await _ws_reject(ws, "未登录或登录已过期")
        return
    if not is_session_member(sid, user.id):
        await _ws_reject(ws, "你不是该世界的成员")
        return

    # Hydrate only after membership — never leave a restored room for strangers.
    sess = get_session(sid)
    if not sess:
        try:
            sess = restore_session(sid)
        except RestoreError as e:
            await _ws_reject(ws, e.message, code=1008)
            return
        except Exception:
            await _ws_reject(ws, "session not found", code=1008)
            return

    bound_player_id: str | None = None
    try:
        # Query player_id, else hello player_id, else membership binding.
        cand = player_id
        if pending_hello and pending_hello.get("player_id"):
            cand = pending_hello.get("player_id")
        bound_player_id = resolve_acting_player_id(sid, user, sess, cand)
    except HTTPException as exc:
        await _ws_reject(ws, str(exc.detail))
        return

    queue = subscribe(sess, player_id=bound_player_id)
    await ws.send_json({
        "type": "snapshot",
        "session": session_dict(sess, viewer_id=bound_player_id),
    })
    if pending_hello and pending_hello.get("type") == "hello":
        await ws.send_json({
            "type": "hello_ack",
            "player_id": bound_player_id,
            "session": session_dict(sess, viewer_id=bound_player_id),
        })

    async def pump_outgoing():
        while True:
            payload = await queue.get()
            if payload.get("type") == "_close":
                try:
                    await ws.close(code=4001)
                except Exception:
                    pass
                return
            await ws.send_json(payload)

    async def server_ping():
        # MP-4 / MP-3: keep-alive so proxies don't idle-drop; client responds with pong/ping.
        while True:
            await asyncio.sleep(25)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                return

    pump_task = asyncio.create_task(pump_outgoing())
    ping_task = asyncio.create_task(server_ping())
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"type": "input", "input": raw}
            t = msg.get("type", "input")

            if t == "hello":
                try:
                    bound_player_id = resolve_acting_player_id(
                        sid, user, sess, msg.get("player_id"),
                    )
                    setattr(queue, "player_id", bound_player_id)
                except HTTPException as exc:
                    await ws.send_json({"type": "error", "message": str(exc.detail)})
                    continue
                await ws.send_json({
                    "type": "hello_ack",
                    "player_id": bound_player_id,
                    "session": session_dict(sess, viewer_id=bound_player_id),
                })
                continue

            try:
                msg_pid = resolve_acting_player_id(
                    sid, user, sess, msg.get("player_id") or bound_player_id,
                )
            except HTTPException as exc:
                await ws.send_json({"type": "error", "message": str(exc.detail)})
                continue

            if t == "input":
                try:
                    rate_limit_play_user(user.id)
                except HTTPException as exc:
                    await ws.send_json({"type": "error", "message": str(exc.detail)})
                    continue
                await step(sess, player_id=msg_pid, player_input=msg.get("input"))
            elif t == "heartbeat":
                await heartbeat(sess, player_id=msg_pid)
            elif t == "sleep":
                await sleep_player(
                    sess, player_id=msg_pid, reason=msg.get("reason", "offline"),
                )
            elif t == "wake":
                await wake_player(sess, player_id=msg_pid)
            elif t == "move":
                try:
                    await move_player(
                        sess,
                        player_id=msg_pid,
                        world_x=float(msg.get("world_x", 0)),
                        world_z=float(msg.get("world_z", 0)),
                    )
                except Exception as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            elif t == "ping":
                await ws.send_json({"type": "pong"})
            elif t == "pong":
                continue
    except WebSocketDisconnect:
        # Disconnect sleeps only THIS connection's player (M2 identity fix).
        # Skip if kicked / already removed from the live roster (MP-2).
        try:
            if bound_player_id and bound_player_id in (sess.player_ids or []):
                await sleep_player(sess, player_id=bound_player_id, reason="disconnect")
        except Exception:
            pass
    finally:
        pump_task.cancel()
        ping_task.cancel()
        unsubscribe(sess, queue)


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        raise exc
    return JSONResponse(status_code=500, content={"error": str(exc)})


# ---------- 3D Generator (Hunyuan3D + procedural maps) ----------
@app.get("/api/generator/status")
async def api_generator_status(user=Depends(get_current_user)):
    status = hunyuan_client.check_status()
    return {"generator": status}


class MapGenerateReq(BaseModel):
    prompt: str
    genre: str | None = None
    civilization: str | None = None


class ModelTextReq(BaseModel):
    prompt: str
    kind: str = "character"  # character | prop
    with_texture: bool = False
    outfit_id: str | None = None  # character wardrobe pack
    civilization: str | None = None  # seed key: ancient|wuxia|…


@app.get("/api/generator/civilizations")
async def api_generator_civilizations(user=Depends(get_current_user)):
    """Civilizations that have curated 3D character + outfit packs."""
    return {"civilizations": list_outfit_civilizations()}


@app.get("/api/generator/outfits")
async def api_generator_outfits(
    user=Depends(get_current_user),
    civilization: str | None = None,
):
    """Selectable clothing + prop packs. Filter with ?civilization=wuxia."""
    return {
        "civilization": civilization,
        "outfits": get_character_outfits(civilization),
    }


@app.post("/api/generator/model/text")
async def api_generator_model_text(req: ModelTextReq, user=Depends(get_current_user)):
    prompt = (req.prompt or "").strip()
    if len(prompt) < 2:
        raise HTTPException(400, "prompt too short")
    if len(prompt) > 500:
        raise HTTPException(400, "prompt too long")
    kind = cast(
        Literal["character", "prop"],
        req.kind if req.kind in ("character", "prop") else "character",
    )
    civ = (req.civilization or "").strip().lower() or None
    outfit_id = req.outfit_id if kind == "character" else None
    if outfit_id and get_outfit(outfit_id, civ) is None:
        raise HTTPException(400, f"unknown outfit_id: {outfit_id}")
    st = hunyuan_client.check_status()
    if not st.get("online"):
        raise HTTPException(503, st.get("message") or "Hunyuan3D 未启动")
    job_id = gen_jobs.create_job(kind, prompt, outfit_id=outfit_id)
    gen_jobs.run_in_background(
        job_id,
        lambda: create_model_job_from_text(
            prompt,
            kind=kind,
            with_texture=req.with_texture,
            job_id=job_id,
            outfit_id=outfit_id,
            civilization=civ,
        ),
    )
    return {
        "job_id": job_id,
        "status": "pending",
        "kind": kind,
        "prompt": prompt,
        "outfit_id": outfit_id,
        "civilization": civ,
    }


@app.get("/api/generator/jobs/{job_id}")
async def api_generator_job_status(job_id: str, user=Depends(get_current_user)):
    job = gen_jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/api/generator/model/image")
async def api_generator_model_image(
    user=Depends(get_current_user),
    image: UploadFile = File(...),
    kind: str = "character",
    prompt: str = "",
    with_texture: bool = False,
    outfit_id: str | None = None,
    civilization: str | None = None,
):
    if kind not in ("character", "prop"):
        kind = "character"
    civ = (civilization or "").strip().lower() or None
    if kind != "character":
        outfit_id = None
    if outfit_id and get_outfit(outfit_id, civ) is None:
        raise HTTPException(400, f"unknown outfit_id: {outfit_id}")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "upload an image file")
    raw = await image.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "image too large (max 12MB)")
    st = hunyuan_client.check_status()
    if not st.get("online"):
        raise HTTPException(503, st.get("message") or "Hunyuan3D 未启动")
    job_id = gen_jobs.create_job(kind, prompt.strip() or None, outfit_id=outfit_id)
    image_bytes = raw

    def _run() -> dict:
        return create_model_job_from_image(
            image_bytes,
            kind=kind,  # type: ignore[arg-type]
            prompt=prompt.strip() or None,
            with_texture=with_texture,
            job_id=job_id,
            outfit_id=outfit_id,
            civilization=civ,
        )

    gen_jobs.run_in_background(job_id, _run)
    return {
        "job_id": job_id,
        "status": "pending",
        "kind": kind,
        "outfit_id": outfit_id,
        "civilization": civ,
    }


@app.get("/api/generator/models/{job_id}/model.glb")
async def api_generator_model_glb(job_id: str, user=Depends(get_current_user)):
    path = get_model_glb_path(job_id)
    if not path:
        raise HTTPException(404, "model not found")
    return FileResponse(path, media_type="model/gltf-binary", filename="model.glb")


@app.post("/api/generator/map")
async def api_generator_map(req: MapGenerateReq, user=Depends(get_current_user)):
    prompt = (req.prompt or "").strip()
    if len(prompt) < 2:
        raise HTTPException(400, "prompt too short")
    if len(prompt) > 500:
        raise HTTPException(400, "prompt too long")
    civ = (req.civilization or req.genre or "").strip().lower() or None
    return create_map_job(prompt, civ)


@app.get("/api/generator/maps/{slug}/preview.png")
async def api_generator_map_png(slug: str, user=Depends(get_current_user)):
    png, _ = get_map_paths(slug)
    if not png:
        raise HTTPException(404, "map not found")
    return FileResponse(png, media_type="image/png")


@app.get("/api/generator/maps/{slug}/meta.json")
async def api_generator_map_meta(slug: str, user=Depends(get_current_user)):
    _, js = get_map_paths(slug)
    if not js:
        raise HTTPException(404, "map not found")
    return JSONResponse(content=json.loads(js.read_text(encoding="utf-8")))


@app.post("/api/generator/character")
async def api_generator_character(
    user=Depends(get_current_user),
    image: UploadFile = File(...),
    with_texture: bool = False,
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "upload an image file")
    raw = await image.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "image too large (max 12MB)")
    result = create_character_job(raw, with_texture=with_texture)
    if result["status"] == "failed":
        raise HTTPException(503, result.get("error") or "generation failed")
    return result


@app.get("/api/generator/characters/{job_id}/model.glb")
async def api_generator_character_glb(job_id: str, user=Depends(get_current_user)):
    path = get_model_glb_path(job_id) or get_character_glb_path(job_id)
    if not path:
        raise HTTPException(404, "model not found")
    return FileResponse(path, media_type="model/gltf-binary", filename="model.glb")

@app.get("/")
async def root():
    return {"name": "Civilization Simulator", "version": "0.4.0"}
