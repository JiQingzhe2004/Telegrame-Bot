from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.runtime_manager import RuntimeManager
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService


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
    app = FastAPI(title="telegram-moderator-bot-api", version="2.0.0")
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

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        state = services.runtime_manager.runtime_state()
        return {
            "status": state["state"],
            "config_complete": state["config_complete"],
        }

    @app.get("/api/v1/runtime/state")
    async def runtime_state() -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.runtime_manager.runtime_state())

    @app.get("/api/v1/setup/state")
    async def setup_state() -> ApiEnvelope:
        runtime = services.runtime_manager.runtime_state()
        return ApiEnvelope(
            ok=True,
            data={
                "state": runtime["state"],
                "config_complete": runtime["config_complete"],
                "runtime_config": services.runtime_manager.get_runtime_config_public(),
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

    @app.get("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def get_settings(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

    @app.put("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def put_settings(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        services.repo.update_settings(chat_id, body)
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

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

    @app.get("/api/v1/chats/{chat_id}/enforcements", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_enforcements(chat_id: int, limit: int = 100) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_enforcements(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/appeals", dependencies=[Depends(require_active), Depends(auth_admin)])
    async def list_appeals(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_appeals(chat_id))

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
