from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.domain.models import ChatRef, MessageRef, ModerationContext, UserRef
from bot.hongbao_service import HongbaoService, PACKET_MODE_EQUAL, PACKET_MODE_RANDOM
from bot.lottery_service import (
    ENTRY_MODE_CONSUME,
    ENTRY_MODE_FREE,
    ENTRY_MODE_THRESHOLD,
    LotteryService,
    PRIZE_SOURCE_PERSONAL,
    PRIZE_SOURCE_POOL,
)
from bot.points_service import PointsService
from bot.runtime_manager import RuntimeManager
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService
from bot.telegram.admin_service import TelegramAdminService
from bot.telegram.lottery import build_winners_summary, send_lottery_announcement
from bot.title_redemption_service import TitleRedemptionService
from bot.utils.time import utc_now
from bot.version import get_backend_version


class ApiEnvelope(BaseModel):
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class Services:
    def __init__(
        self,
        repo: BotRepository,
        config_service: ConfigService,
        runtime_manager: RuntimeManager,
        cors_origins: tuple[str, ...],
        web_admin_dist_path: Path,
    ) -> None:
        self.repo = repo
        self.config_service = config_service
        self.runtime_manager = runtime_manager
        self.cors_origins = cors_origins
        self.web_admin_dist_path = web_admin_dist_path


def create_http_app(services: Services, webhook_path: str) -> FastAPI:
    backend_version = get_backend_version()
    app = FastAPI(title="telegram-moderator-bot-api", version=backend_version)
    points_service = PointsService(services.repo)
    hongbao_service = HongbaoService(services.repo)
    lottery_service = LotteryService(services.repo)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(services.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_active() -> None:
        if not services.runtime_manager.is_active():
            raise HTTPException(status_code=409, detail="setup_required")

    def auth_admin(x_admin_token: str = Header(default="")) -> None:
        if not services.runtime_manager.verify_admin_token(x_admin_token):
            raise HTTPException(status_code=401, detail="unauthorized")

    def auth_setup_token(x_setup_token: str = Header(default="")) -> str:
        if not x_setup_token:
            raise HTTPException(status_code=401, detail="missing_setup_token")
        if not services.config_service.verify_setup_token(x_setup_token, consume=False):
            raise HTTPException(status_code=401, detail="invalid_setup_token")
        return x_setup_token

    def _is_loopback(request: Request) -> bool:
        if not request.client:
            return False
        return request.client.host in {"127.0.0.1", "localhost", "::1"}

    def _get_known_chat(chat_id: int) -> dict[str, Any]:
        chat = services.repo.get_chat(chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="chat_not_found")
        return chat

    def _get_ai_runtime():
        ai_moderator = services.runtime_manager.get_ai_moderator()
        if ai_moderator is None:
            raise HTTPException(status_code=503, detail="ai_runtime_unavailable")
        return ai_moderator

    def _get_time_of_day(hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 22:
            return "evening"
        return "night"

    def _parse_verification_question_payload(chat_id: int, body: dict[str, Any]) -> dict[str, Any]:
        question = str(body.get("question", "")).strip()
        if not question:
            raise HTTPException(status_code=400, detail="missing_question")

        raw_options = body.get("options")
        if not isinstance(raw_options, list):
            raise HTTPException(status_code=400, detail="invalid_options")
        options = [str(item).strip() for item in raw_options if str(item).strip()]
        if len(options) < 2 or len(options) > 4:
            raise HTTPException(status_code=400, detail="invalid_options")

        try:
            answer_index = int(body.get("answer_index", -1))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_answer_index") from exc
        if answer_index < 0 or answer_index >= len(options):
            raise HTTPException(status_code=400, detail="invalid_answer_index")

        scope = str(body.get("scope", "chat")).strip().lower() or "chat"
        if scope not in {"chat", "global"}:
            raise HTTPException(status_code=400, detail="invalid_scope")

        return {
            "chat_id": None if scope == "global" else chat_id,
            "scope": scope,
            "question": question,
            "options": options,
            "answer_index": answer_index,
        }

    def _parse_verification_generate_payload(chat_id: int, body: dict[str, Any]) -> dict[str, Any]:
        scope = str(body.get("scope", "chat")).strip().lower() or "chat"
        if scope not in {"chat", "global"}:
            raise HTTPException(status_code=400, detail="invalid_scope")
        try:
            count = int(body.get("count", 3))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_count") from exc
        if count < 1 or count > 5:
            raise HTTPException(status_code=400, detail="invalid_count")
        topic_hint = str(body.get("topic_hint", "")).strip()
        return {
            "chat_id": None if scope == "global" else chat_id,
            "scope": scope,
            "count": count,
            "topic_hint": topic_hint,
        }

    def _parse_lottery_payload(chat_id: int, body: dict[str, Any]) -> dict[str, Any]:
        title = str(body.get("title", "")).strip()
        if not title:
            raise HTTPException(status_code=400, detail="missing_lottery_title")
        entry_mode = str(body.get("entry_mode", ENTRY_MODE_FREE)).strip() or ENTRY_MODE_FREE
        if entry_mode not in {ENTRY_MODE_FREE, ENTRY_MODE_CONSUME, ENTRY_MODE_THRESHOLD}:
            raise HTTPException(status_code=400, detail="invalid_lottery_entry_mode")
        prizes = body.get("prizes")
        if not isinstance(prizes, list) or not prizes:
            raise HTTPException(status_code=400, detail="invalid_lottery_prizes")
        parsed_prizes = []
        for idx, prize in enumerate(prizes):
            if not isinstance(prize, dict):
                raise HTTPException(status_code=400, detail="invalid_lottery_prizes")
            prize_title = str(prize.get("title", "")).strip()
            if not prize_title:
                raise HTTPException(status_code=400, detail="invalid_lottery_prize_title")
            parsed_prizes.append(
                {
                    "title": prize_title,
                    "winner_count": max(int(prize.get("winner_count", 1)), 0),
                    "bonus_points": max(int(prize.get("bonus_points", 0)), 0),
                    "sort_order": int(prize.get("sort_order", idx)),
                }
            )
        starts_at = str(body.get("starts_at", "")).strip()
        entry_deadline_at = str(body.get("entry_deadline_at", "")).strip()
        draw_at = str(body.get("draw_at", "")).strip() or entry_deadline_at
        if not starts_at or not entry_deadline_at or not draw_at:
            raise HTTPException(status_code=400, detail="missing_lottery_schedule")
        try:
            starts_dt = services.repo.parse_iso_datetime(starts_at)
            deadline_dt = services.repo.parse_iso_datetime(entry_deadline_at)
            draw_dt = services.repo.parse_iso_datetime(draw_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_lottery_schedule") from exc
        if deadline_dt < starts_dt or draw_dt < deadline_dt:
            raise HTTPException(status_code=400, detail="invalid_lottery_schedule_order")
        max_entries_per_user = max(int(body.get("max_entries_per_user", 1)), 1)
        prize_source = str(body.get("prize_source", PRIZE_SOURCE_PERSONAL)).strip() or PRIZE_SOURCE_PERSONAL
        if prize_source not in {PRIZE_SOURCE_PERSONAL, PRIZE_SOURCE_POOL}:
            raise HTTPException(status_code=400, detail="invalid_lottery_prize_source")
        total_bonus_points = sum(int(item["bonus_points"]) * int(item["winner_count"]) for item in parsed_prizes)
        if prize_source == PRIZE_SOURCE_POOL:
            pool = services.repo.get_points_pool_balance(chat_id)
            if int(pool["balance"]) < total_bonus_points:
                raise HTTPException(status_code=400, detail="lottery_pool_insufficient")
        return {
            "chat_id": chat_id,
            "title": title,
            "description": str(body.get("description", "")).strip(),
            "entry_mode": entry_mode,
            "points_cost": max(int(body.get("points_cost", 0)), 0),
            "points_threshold": max(int(body.get("points_threshold", 0)), 0),
            "allow_multiple_entries": bool(body.get("allow_multiple_entries", False)),
            "max_entries_per_user": max_entries_per_user,
            "show_participants": bool(body.get("show_participants", True)),
            "prize_source": prize_source,
            "starts_at": starts_at,
            "entry_deadline_at": entry_deadline_at,
            "draw_at": draw_at,
            "created_by": int(body.get("created_by", 0) or 0) or None,
            "prizes": parsed_prizes,
        }

    def _points_settings_payload(body: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "points_enabled",
            "points_message_reward",
            "points_message_cooldown_seconds",
            "points_daily_cap",
            "points_transfer_enabled",
            "points_transfer_min_amount",
            "hongbao_template",
        }
        payload = {k: body[k] for k in allowed if k in body}
        if "points_message_reward" in payload:
            payload["points_message_reward"] = int(payload["points_message_reward"])
        if "points_message_cooldown_seconds" in payload:
            payload["points_message_cooldown_seconds"] = int(payload["points_message_cooldown_seconds"])
        if "points_daily_cap" in payload:
            payload["points_daily_cap"] = int(payload["points_daily_cap"])
        if "points_transfer_min_amount" in payload:
            payload["points_transfer_min_amount"] = int(payload["points_transfer_min_amount"])
        if "hongbao_template" in payload:
            payload["hongbao_template"] = str(payload["hongbao_template"])
        return payload

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        state = services.runtime_manager.runtime_state()
        return {
            "status": state["state"],
            "config_complete": state["config_complete"],
            "backend_version": backend_version,
        }

    @app.get("/api/v1/runtime/state")
    async def runtime_state() -> ApiEnvelope:
        return ApiEnvelope(
            ok=True,
            data={
                **services.runtime_manager.runtime_state(),
                "backend_version": backend_version,
            },
        )

    @app.get("/api/v1/setup/state")
    async def setup_state() -> ApiEnvelope:
        runtime = services.runtime_manager.runtime_state()
        return ApiEnvelope(
            ok=True,
            data={
                "state": runtime["state"],
                "config_complete": runtime["config_complete"],
                "backend_version": backend_version,
                "runtime_config": services.runtime_manager.get_runtime_config_public(),
            },
        )

    @app.post("/api/v1/auth/login")
    async def auth_login(body: dict[str, str]) -> ApiEnvelope:
        if not services.runtime_manager.is_active():
            raise HTTPException(status_code=409, detail="setup_required")
        token = body.get("admin_token", "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="missing_admin_token")
        if not services.runtime_manager.verify_admin_token(token):
            raise HTTPException(status_code=401, detail="unauthorized")
        return ApiEnvelope(
            ok=True,
            data={
                "authenticated": True,
                "backend_version": backend_version,
                "runtime_state": services.runtime_manager.runtime_state(),
            },
        )

    @app.post("/api/v1/setup/auth")
    async def setup_auth(body: dict[str, str]) -> ApiEnvelope:
        if services.runtime_manager.is_active():
            raise HTTPException(status_code=409, detail="already_active")
        code = body.get("code", "").strip()
        if not code:
            raise HTTPException(status_code=400, detail="missing_code")
        if not services.config_service.verify_bootstrap_code(code):
            raise HTTPException(status_code=401, detail="invalid_code")
        setup_token = services.config_service.issue_setup_token()
        return ApiEnvelope(ok=True, data={"setup_token": setup_token, "expires_in_minutes": 30})

    @app.post("/api/v1/setup/reissue-code")
    async def setup_reissue_code(request: Request) -> ApiEnvelope:
        if services.runtime_manager.is_active():
            raise HTTPException(status_code=409, detail="already_active")
        if not _is_loopback(request):
            raise HTTPException(status_code=403, detail="loopback_only")
        code = services.config_service.issue_bootstrap_code(ttl_minutes=20)
        return ApiEnvelope(ok=True, data={"code": code, "expires_in_minutes": 20})

    @app.post("/api/v1/setup/config", dependencies=[Depends(auth_setup_token)])
    async def setup_config(body: dict[str, Any]) -> ApiEnvelope:
        try:
            conf = services.runtime_manager.update_runtime_config(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_config", "errors": str(exc)}) from exc
        return ApiEnvelope(ok=True, data={"saved": True, "config": conf.redacted()})

    @app.post("/api/v1/setup/activate")
    async def setup_activate(x_setup_token: str = Header(default="")) -> ApiEnvelope:
        if not services.config_service.verify_setup_token(x_setup_token, consume=True):
            raise HTTPException(status_code=401, detail="invalid_setup_token")
        activation_errors = services.config_service.validate_activation()
        if activation_errors:
            raise HTTPException(status_code=400, detail={"code": "invalid_config", "errors": activation_errors})
        await services.runtime_manager.reload()
        state = services.runtime_manager.runtime_state()
        if state["state"] != "active":
            raise HTTPException(status_code=500, detail="activate_failed")
        return ApiEnvelope(ok=True, data=state)

    @app.post(webhook_path)
    async def telegram_webhook(request: Request) -> JSONResponse:
        payload = await request.json()
        if not services.runtime_manager.is_active():
            raise HTTPException(status_code=409, detail="setup_required")
        await services.runtime_manager.process_webhook_update(payload)
        return JSONResponse({"ok": True})

    @app.get("/api/v1/status", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def status() -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.status_summary())

    @app.get("/api/v1/runtime/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_runtime_config() -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.runtime_manager.get_runtime_config_public())

    @app.put("/api/v1/runtime/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_runtime_config(body: dict[str, Any]) -> ApiEnvelope:
        allowed = {
            "openai_api_key",
            "openai_base_url",
            "ai_low_risk_model",
            "ai_high_risk_model",
            "ai_timeout_seconds",
            "join_verification_enabled",
            "join_verification_timeout_seconds",
            "join_verification_question_type",
            "join_verification_max_attempts",
            "join_verification_whitelist_bypass",
            "join_welcome_enabled",
            "join_welcome_use_ai",
            "join_welcome_template",
            "run_mode",
            "webhook_public_url",
            "webhook_path",
        }
        payload = {k: v for k, v in body.items() if k in allowed}
        if not payload:
            raise HTTPException(status_code=400, detail="missing_runtime_config_fields")
        try:
            conf = services.runtime_manager.update_runtime_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_config", "errors": str(exc)}) from exc
        await services.runtime_manager.reload(conf)
        return ApiEnvelope(ok=True, data={"runtime_config": conf.redacted(), "state": services.runtime_manager.runtime_state()})

    @app.post("/api/v1/runtime/telegram/commands/sync", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def sync_telegram_commands() -> ApiEnvelope:
        try:
            await services.runtime_manager.sync_bot_commands()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail="runtime_not_active") from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"telegram_command_sync_failed: {exc}") from exc
        return ApiEnvelope(ok=True, data={"synced": True})

    @app.get("/api/v1/chats", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_chats(limit: int = 200) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_chats(limit))

    @app.get("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_settings(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

    @app.put("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_settings(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        services.repo.update_settings(chat_id, body)
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

    @app.get("/api/v1/chats/{chat_id}/points/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_config(chat_id: int) -> ApiEnvelope:
        settings = services.repo.get_settings(chat_id)
        return ApiEnvelope(
            ok=True,
            data={
                "points_enabled": settings.points_enabled,
                "points_message_reward": settings.points_message_reward,
                "points_message_cooldown_seconds": settings.points_message_cooldown_seconds,
                "points_daily_cap": settings.points_daily_cap,
                "points_transfer_enabled": settings.points_transfer_enabled,
                "points_transfer_min_amount": settings.points_transfer_min_amount,
            },
        )

    @app.put("/api/v1/chats/{chat_id}/points/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_points_config(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        payload = _points_settings_payload(body)
        if not payload:
            raise HTTPException(status_code=400, detail="missing_points_config_fields")
        services.repo.update_settings(chat_id, payload)
        settings = services.repo.get_settings(chat_id)
        return ApiEnvelope(
            ok=True,
            data={
                "points_enabled": settings.points_enabled,
                "points_message_reward": settings.points_message_reward,
                "points_message_cooldown_seconds": settings.points_message_cooldown_seconds,
                "points_daily_cap": settings.points_daily_cap,
                "points_transfer_enabled": settings.points_transfer_enabled,
                "points_transfer_min_amount": settings.points_transfer_min_amount,
            },
        )

    @app.get("/api/v1/chats/{chat_id}/points/balance/{user_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_balance(chat_id: int, user_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.get_points_balance(chat_id, user_id))

    @app.get("/api/v1/chats/{chat_id}/points/leaderboard", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_leaderboard(chat_id: int, limit: int = 20) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.list_points_leaderboard(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/points/ledger", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_ledger(chat_id: int, limit: int = 100, user_id: int | None = None) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.list_points_ledger(chat_id, limit=limit, user_id=user_id))

    @app.post("/api/v1/chats/{chat_id}/points/adjust", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def adjust_points(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        try:
            user_id = int(body.get("user_id", 0))
            amount = int(body.get("amount", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_points_adjust") from exc
        if not user_id:
            raise HTTPException(status_code=400, detail="missing_user_id")
        try:
            result = services.repo.adjust_points(
                chat_id=chat_id,
                user_id=user_id,
                amount=amount,
                event_type="admin_adjust",
                operator="admin_api",
                reason=str(body.get("reason", "")).strip() or "admin_adjust",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiEnvelope(ok=True, data=result)

    @app.get("/api/v1/chats/{chat_id}/points/checkin/state", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_checkin_state(chat_id: int, user_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=points_service.get_checkin_state(chat_id, user_id))

    @app.post("/api/v1/chats/{chat_id}/points/checkin", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def points_checkin(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        try:
            user_id = int(body.get("user_id", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_user_id") from exc
        if not user_id:
            raise HTTPException(status_code=400, detail="missing_user_id")
        try:
            result = points_service.checkin(chat_id, user_id, services.repo.get_settings(chat_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiEnvelope(ok=True, data=result)

    @app.get("/api/v1/chats/{chat_id}/points/tasks", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_tasks(chat_id: int, user_id: int | None = None) -> ApiEnvelope:
        _get_known_chat(chat_id)
        if user_id is None:
            return ApiEnvelope(ok=True, data=points_service.list_task_config(chat_id))
        return ApiEnvelope(ok=True, data=points_service.list_tasks_for_user(chat_id, user_id))

    @app.get("/api/v1/chats/{chat_id}/points/tasks/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_tasks_config(chat_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=points_service.list_task_config(chat_id))

    @app.put("/api/v1/chats/{chat_id}/points/tasks/config", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_points_tasks_config(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        items = body.get("items")
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="invalid_task_items")
        return ApiEnvelope(ok=True, data=points_service.update_task_config(chat_id, items))

    @app.get("/api/v1/chats/{chat_id}/points/shop", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_shop(chat_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=points_service.list_shop(chat_id))

    @app.put("/api/v1/chats/{chat_id}/points/shop", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_points_shop(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        items = body.get("items")
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="invalid_shop_items")
        return ApiEnvelope(ok=True, data=points_service.update_shop(chat_id, items))

    @app.post("/api/v1/chats/{chat_id}/points/redeem", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def post_points_redeem(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        try:
            user_id = int(body.get("user_id", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_user_id") from exc
        item_key = str(body.get("item_key", "")).strip()
        if not user_id or not item_key:
            raise HTTPException(status_code=400, detail="missing_redeem_fields")
        try:
            result = points_service.redeem(chat_id, user_id, item_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        item = result.get("item") or {}
        meta = item.get("meta") if isinstance(item, dict) else {}
        if str(item.get("item_type")) == "leaderboard_title" and bool(meta.get("auto_approve")) and str(meta.get("title_mode")) == "fixed":
            applied = await _title_redemption_service().apply_redemption(int(result["redemption"]["id"]))
            result["redemption"] = applied.redemption or result["redemption"]
        return ApiEnvelope(ok=True, data=result)

    @app.get("/api/v1/chats/{chat_id}/points/redemptions", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_redemptions(chat_id: int, user_id: int | None = None, limit: int = 100) -> ApiEnvelope:
        _get_known_chat(chat_id)
        data = points_service.list_redemptions(chat_id, user_id=user_id)
        return ApiEnvelope(ok=True, data=data[:limit])

    @app.get("/api/v1/chats/{chat_id}/points/packets", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_packets(chat_id: int, limit: int = 100) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.list_points_packets(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/points/packets/{packet_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_packet(chat_id: int, packet_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        packet = services.repo.get_points_packet(packet_id)
        if packet is None or int(packet["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="packet_not_found")
        return ApiEnvelope(ok=True, data={**packet, "claims": services.repo.list_points_packet_claims(packet_id)})

    @app.post("/api/v1/chats/{chat_id}/points/packets", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def create_points_packet(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        try:
            sender_user_id = int(body.get("sender_user_id", 0))
            total_amount = int(body.get("total_amount", 0))
            packet_count = int(body.get("packet_count", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_packet_fields") from exc
        split_mode = str(body.get("split_mode", PACKET_MODE_RANDOM)).strip() or PACKET_MODE_RANDOM
        blessing = str(body.get("blessing", "")).strip()
        if split_mode not in {PACKET_MODE_RANDOM, PACKET_MODE_EQUAL}:
            raise HTTPException(status_code=400, detail="invalid_packet_split_mode")
        try:
            result = hongbao_service.create_packet(
                chat_id=chat_id,
                sender_user_id=sender_user_id,
                total_amount=total_amount,
                packet_count=packet_count,
                split_mode=split_mode,
                blessing=blessing,
                settings=services.repo.get_settings(chat_id),
                operator="admin_api",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiEnvelope(ok=True, data=result)

    @app.get("/api/v1/chats/{chat_id}/points/pool", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_pool(chat_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.get_points_pool_balance(chat_id))

    @app.get("/api/v1/chats/{chat_id}/points/pool/ledger", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_points_pool_ledger(chat_id: int, limit: int = 100) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.list_points_pool_ledger(chat_id, limit))

    @app.post("/api/v1/chats/{chat_id}/points/pool/adjust", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def post_points_pool_adjust(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        try:
            amount = int(body.get("amount", 0))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_pool_amount") from exc
        reason = str(body.get("reason", "")).strip()
        try:
            row = services.repo.adjust_points_pool(
                chat_id=chat_id,
                amount=amount,
                operator="admin_api",
                reason=reason,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiEnvelope(ok=True, data=row)

    @app.post("/api/v1/chats/{chat_id}/points/redemptions/{redemption_id}/status", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def post_points_redemption_status(chat_id: int, redemption_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        status = str(body.get("status", "")).strip().lower()
        if status not in {"pending", "pending_input", "active", "rejected", "consumed", "expired", "failed"}:
            raise HTTPException(status_code=400, detail="invalid_redemption_status")
        current = services.repo.get_redemption(redemption_id)
        if current is None:
            raise HTTPException(status_code=404, detail="redemption_not_found")
        if str(current.get("item_type")) == "leaderboard_title" and status == "active":
            if str(current.get("status")) == "pending_input":
                raise HTTPException(status_code=400, detail="custom_title_not_submitted")
            applied = await _title_redemption_service().apply_redemption(redemption_id)
            row = applied.redemption
        else:
            row = points_service.update_redemption_status(redemption_id, status)
        if row is None:
            raise HTTPException(status_code=404, detail="redemption_not_found")
        return ApiEnvelope(ok=True, data=row)

    @app.get("/api/v1/chats/{chat_id}/lotteries", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_lotteries(chat_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=lottery_service.list_lotteries(chat_id))

    @app.post("/api/v1/chats/{chat_id}/lotteries", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def create_lottery(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        payload = _parse_lottery_payload(chat_id, body)
        created = lottery_service.create_lottery(chat_id, payload)
        tg_app = services.runtime_manager.get_bot_application()
        if tg_app is not None:
            message_id = await send_lottery_announcement(
                bot=tg_app.bot,
                chat_id=chat_id,
                lottery=created,
                prizes=created["prizes"],
                stats=created["stats"],
            )
            if message_id:
                services.repo.set_lottery_announcement_message(int(created["id"]), message_id)
                created = lottery_service.get_lottery_detail(int(created["id"]))
        return ApiEnvelope(ok=True, data=created)

    @app.get("/api/v1/chats/{chat_id}/lotteries/{lottery_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_lottery(chat_id: int, lottery_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        detail = lottery_service.get_lottery_detail(lottery_id)
        if int(detail["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="lottery_not_found")
        return ApiEnvelope(ok=True, data=detail)

    @app.put("/api/v1/chats/{chat_id}/lotteries/{lottery_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def update_lottery(chat_id: int, lottery_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        payload = _parse_lottery_payload(chat_id, body)
        updated = lottery_service.update_lottery(lottery_id, payload)
        if int(updated["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="lottery_not_found")
        return ApiEnvelope(ok=True, data=updated)

    @app.get("/api/v1/chats/{chat_id}/lotteries/{lottery_id}/entries", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_lottery_entries(chat_id: int, lottery_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        detail = lottery_service.get_lottery_detail(lottery_id)
        if int(detail["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="lottery_not_found")
        return ApiEnvelope(ok=True, data=services.repo.list_lottery_entries(lottery_id))

    @app.post("/api/v1/chats/{chat_id}/lotteries/{lottery_id}/cancel", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def cancel_lottery(chat_id: int, lottery_id: int, body: dict[str, Any] | None = None) -> ApiEnvelope:
        _get_known_chat(chat_id)
        canceled = lottery_service.cancel_lottery(lottery_id, operator="admin_api")
        if int(canceled["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="lottery_not_found")
        tg_app = services.runtime_manager.get_bot_application()
        if tg_app is not None:
            await tg_app.bot.send_message(chat_id=chat_id, text=f"抽奖活动「{canceled['title']}」已取消。")
        return ApiEnvelope(ok=True, data=canceled)

    @app.post("/api/v1/chats/{chat_id}/lotteries/{lottery_id}/draw", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def draw_lottery(chat_id: int, lottery_id: int, body: dict[str, Any] | None = None) -> ApiEnvelope:
        _get_known_chat(chat_id)
        detail = lottery_service.draw_lottery(lottery_id, operator="admin_api")
        if int(detail["chat_id"]) != chat_id:
            raise HTTPException(status_code=404, detail="lottery_not_found")
        tg_app = services.runtime_manager.get_bot_application()
        if tg_app is not None:
            await tg_app.bot.send_message(chat_id=chat_id, text=build_winners_summary(detail, detail["winners"]))
        return ApiEnvelope(ok=True, data=detail)

    @app.get("/api/v1/chats/{chat_id}/verification/questions", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_verification_questions(chat_id: int, include_global: bool = True) -> ApiEnvelope:
        _get_known_chat(chat_id)
        return ApiEnvelope(ok=True, data=services.repo.list_verification_questions(chat_id, include_global=include_global))

    @app.post("/api/v1/chats/{chat_id}/verification/questions", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def create_verification_question(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        payload = _parse_verification_question_payload(chat_id, body)
        item = services.repo.create_verification_question(
            chat_id=payload["chat_id"],
            question=payload["question"],
            options=payload["options"],
            answer_index=payload["answer_index"],
        )
        return ApiEnvelope(ok=True, data=item)

    @app.post("/api/v1/chats/{chat_id}/verification/questions/generate", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def generate_verification_questions(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        chat = _get_known_chat(chat_id)
        payload = _parse_verification_generate_payload(chat_id, body)
        settings = services.repo.get_settings(chat_id)
        try:
            result = await _get_ai_runtime().generate_verification_questions_result(
                chat_title=chat.get("title") or "群聊",
                language=settings.language,
                count=payload["count"],
                topic_hint=payload["topic_hint"] or None,
                chat_type=chat.get("type"),
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"ai_generate_failed: {exc}") from exc
        created = [
            services.repo.create_verification_question(
                chat_id=payload["chat_id"],
                question=item.question,
                options=item.options,
                answer_index=item.answer_index,
            )
            for item in result.items
        ]
        return ApiEnvelope(
            ok=True,
            data={
                "model": result.model,
                "count": len(created),
                "items": created,
            },
        )

    @app.put("/api/v1/chats/{chat_id}/verification/questions/{question_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def update_verification_question(chat_id: int, question_id: int, body: dict[str, Any]) -> ApiEnvelope:
        _get_known_chat(chat_id)
        payload = _parse_verification_question_payload(chat_id, body)
        item = services.repo.update_verification_question(
            access_chat_id=chat_id,
            question_id=question_id,
            target_chat_id=payload["chat_id"],
            question=payload["question"],
            options=payload["options"],
            answer_index=payload["answer_index"],
        )
        if item is None:
            raise HTTPException(status_code=404, detail="verification_question_not_found")
        return ApiEnvelope(ok=True, data=item)

    @app.delete("/api/v1/chats/{chat_id}/verification/questions/{question_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def delete_verification_question(chat_id: int, question_id: int) -> ApiEnvelope:
        _get_known_chat(chat_id)
        deleted = services.repo.delete_verification_question(chat_id, question_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="verification_question_not_found")
        return ApiEnvelope(ok=True, data={"deleted": deleted})

    @app.get("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_whitelist(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_items("whitelists", chat_id))

    @app.post("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def add_whitelist(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        services.repo.add_list_item("whitelists", chat_id, body.get("type", "user"), body["value"])
        return ApiEnvelope(ok=True, data={"created": True})

    @app.delete("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def delete_whitelist(chat_id: int, value: str, item_type: str = "user") -> ApiEnvelope:
        deleted = services.repo.delete_list_item("whitelists", chat_id, item_type, value)
        return ApiEnvelope(ok=True, data={"deleted": deleted})

    @app.get("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_blacklist(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_items("blacklists", chat_id))

    @app.post("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def add_blacklist(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        services.repo.add_list_item("blacklists", chat_id, body.get("type", "word"), body["value"])
        return ApiEnvelope(ok=True, data={"created": True})

    @app.delete("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def delete_blacklist(chat_id: int, value: str, item_type: str = "word") -> ApiEnvelope:
        deleted = services.repo.delete_list_item("blacklists", chat_id, item_type, value)
        return ApiEnvelope(ok=True, data={"deleted": deleted})

    @app.get("/api/v1/chats/{chat_id}/audits", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_audits(chat_id: int, limit: int = 100) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_audits(chat_id, limit))

    @app.post("/api/v1/chats/{chat_id}/ai-test/moderation", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def test_moderation_ai(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        text = body.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="missing_text")

        chat = _get_known_chat(chat_id)
        settings = services.repo.get_settings(chat_id)
        message = MessageRef(
            chat_id=chat_id,
            message_id=0,
            user_id=0,
            date=utc_now(),
            text=text,
            meta={"source": "admin_ai_test"},
        )
        context = ModerationContext(
            chat=ChatRef(chat_id=chat_id, type=chat.get("type") or "supergroup", title=chat.get("title")),
            user=UserRef(user_id=0, username="admin_ai_test", is_bot=False, first_name="AI", last_name="Test"),
            settings=settings,
            strike_score=0,
            whitelist_hit=False,
            blacklist_words=services.repo.get_blacklist_words(chat_id),
            recent_message_texts=[],
        )
        started_at = perf_counter()
        try:
            decision = await _get_ai_runtime().classify(message, context)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"ai_test_failed: {exc}") from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        return ApiEnvelope(
            ok=True,
            data={
                "chat_ai_enabled": settings.ai_enabled,
                "model": decision.raw.get("_model"),
                "category": decision.category,
                "level": decision.level,
                "confidence": decision.confidence,
                "suggested_action": decision.suggested_action,
                "reasons": decision.reasons,
                "latency_ms": latency_ms,
            },
        )

    @app.post("/api/v1/chats/{chat_id}/ai-test/welcome", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def test_welcome_ai(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        user_display_name = body.get("user_display_name", "").strip()
        if not user_display_name:
            raise HTTPException(status_code=400, detail="missing_user_display_name")

        chat = _get_known_chat(chat_id)
        settings = services.repo.get_settings(chat_id)
        runtime_config = services.runtime_manager.get_runtime_config_raw()

        now_hour = datetime.now(tz=timezone.utc).hour
        chosen_template = runtime_config.join_welcome_template
        templates = services.repo.list_welcome_templates(chat_id, hour=now_hour, chat_type=chat.get("type"))
        if templates:
            chosen_template = templates[0]["template"]

        started_at = perf_counter()
        try:
            result = await _get_ai_runtime().generate_welcome_result(
                chat_title=chat.get("title") or "群聊",
                user_display_name=user_display_name,
                language=settings.language,
                template=chosen_template,
                time_of_day=_get_time_of_day(now_hour),
                chat_type=chat.get("type"),
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"ai_test_failed: {exc}") from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        return ApiEnvelope(
            ok=True,
            data={
                "join_welcome_enabled": runtime_config.join_welcome_enabled,
                "join_welcome_use_ai": runtime_config.join_welcome_use_ai,
                "model": result.model,
                "text": result.text,
                "template": chosen_template,
                "latency_ms": latency_ms,
            },
        )

    @app.get("/api/v1/chats/{chat_id}/enforcements", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_enforcements(chat_id: int, limit: int = 100) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_enforcements(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/appeals", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_appeals(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_appeals(chat_id))

    def _admin_service() -> TelegramAdminService:
        tg_app = services.runtime_manager.get_bot_application()
        if not tg_app:
            raise HTTPException(status_code=409, detail="runtime_not_active")
        return TelegramAdminService(tg_app.bot, services.repo)

    def _title_redemption_service() -> TitleRedemptionService:
        tg_app = services.runtime_manager.get_bot_application()
        if not tg_app:
            raise HTTPException(status_code=409, detail="runtime_not_active")
        return TitleRedemptionService(services.repo, tg_app.bot)

    @app.get("/api/v1/chats/{chat_id}/admin/overview", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_overview(chat_id: int) -> ApiEnvelope:
        svc = _admin_service()
        data = await svc.overview(chat_id)
        return ApiEnvelope(ok=True, data=data)

    @app.get("/api/v1/chats/{chat_id}/admin/members", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_members(chat_id: int, limit: int = 200, q: str = "") -> ApiEnvelope:
        svc = _admin_service()
        rows = await svc.list_members(chat_id=chat_id, limit=limit, query=q)
        return ApiEnvelope(ok=True, data=rows)

    @app.get("/api/v1/chats/{chat_id}/admin/members/{user_id}", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_member(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.get_member(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.put("/api/v1/chats/{chat_id}/admin/profile", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_update_profile(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.update_profile(chat_id, body.get("title"), body.get("description"))
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/messages/{message_id}/delete", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_delete_message(chat_id: int, message_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.delete_message(chat_id, message_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/messages/{message_id}/pin", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_pin_message(chat_id: int, message_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.pin_message(chat_id, message_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/messages/unpin", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_unpin_message(chat_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.unpin_message(chat_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/members/{user_id}/mute", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_mute_member(chat_id: int, user_id: int, body: dict[str, Any]) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.mute_member(chat_id, user_id, int(body.get("duration_seconds", 600)))
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/members/{user_id}/unmute", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_unmute_member(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.unmute_member(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/members/{user_id}/ban", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_ban_member(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.ban_member(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/members/{user_id}/kick", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_kick_member(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.kick_member(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/members/{user_id}/unban", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_unban_member(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.unban_member(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/invite-links/create", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_create_invite(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.create_invite_link(chat_id, body.get("name"))
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/invite-links/revoke", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_revoke_invite(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        svc = _admin_service()
        link = str(body.get("invite_link", "")).strip()
        if not link:
            raise HTTPException(status_code=400, detail="missing_invite_link")
        result = await svc.revoke_invite_link(chat_id, link)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/admins/{user_id}/promote", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_promote(chat_id: int, user_id: int, body: dict[str, Any]) -> ApiEnvelope:
        svc = _admin_service()
        permissions = {
            "can_manage_chat": bool(body.get("can_manage_chat", True)),
            "can_change_info": bool(body.get("can_change_info", False)),
            "can_delete_messages": bool(body.get("can_delete_messages", True)),
            "can_invite_users": bool(body.get("can_invite_users", True)),
            "can_restrict_members": bool(body.get("can_restrict_members", True)),
            "can_pin_messages": bool(body.get("can_pin_messages", True)),
            "can_promote_members": bool(body.get("can_promote_members", False)),
            "can_manage_video_chats": bool(body.get("can_manage_video_chats", True)),
            "can_post_stories": bool(body.get("can_post_stories", False)),
            "can_edit_stories": bool(body.get("can_edit_stories", False)),
            "can_delete_stories": bool(body.get("can_delete_stories", False)),
            "is_anonymous": bool(body.get("is_anonymous", False)),
        }
        result = await svc.promote_admin(chat_id, user_id, permissions)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/admins/{user_id}/demote", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_demote(chat_id: int, user_id: int) -> ApiEnvelope:
        svc = _admin_service()
        result = await svc.demote_admin(chat_id, user_id)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/chats/{chat_id}/admin/admins/{user_id}/title", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def admin_title(chat_id: int, user_id: int, body: dict[str, Any]) -> ApiEnvelope:
        title = str(body.get("title", "")).strip()
        if not title:
            raise HTTPException(status_code=400, detail="missing_title")
        svc = _admin_service()
        result = await svc.set_admin_title(chat_id, user_id, title)
        return ApiEnvelope(ok=True, data=result.__dict__)

    @app.post("/api/v1/enforcements/{enforcement_id}/rollback", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def rollback(enforcement_id: int) -> ApiEnvelope:
        data = services.repo.get_enforcement(enforcement_id)
        if not data:
            raise HTTPException(status_code=404, detail="enforcement not found")
        tg_app = services.runtime_manager.get_bot_application()
        enforcer = services.runtime_manager.get_enforcer()
        if not tg_app or not enforcer:
            raise HTTPException(status_code=409, detail="runtime_not_active")
        ok, reason = await enforcer.rollback(
            tg_app.bot,
            chat_id=int(data["chat_id"]),
            user_id=int(data["user_id"]),
            action=data["action"],
        )
        services.repo.add_rollback(
            enforcement_id=enforcement_id,
            chat_id=int(data["chat_id"]),
            user_id=int(data["user_id"]),
            status="ok" if ok else "failed",
            reason=reason,
        )
        return ApiEnvelope(ok=ok, data={"reason": reason})

    if services.web_admin_dist_path.exists():
        app.mount("/", StaticFiles(directory=str(services.web_admin_dist_path), html=True), name="web_admin")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def setup_hint() -> str:
            return (
                "<h2>管理前端未构建</h2>"
                "<p>请执行 <code>python -m bot.bootstrap</code> 或进入 <code>web-admin</code> 执行 <code>npm run build</code>。</p>"
            )

    return app
