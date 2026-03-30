from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application

from bot.domain.moderation import Enforcer
from bot.storage.repo import BotRepository


class ApiEnvelope(BaseModel):
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class Services:
    def __init__(self, repo: BotRepository, admin_token: str, tg_app: Application, enforcer: Enforcer) -> None:
        self.repo = repo
        self.admin_token = admin_token
        self.tg_app = tg_app
        self.enforcer = enforcer


def create_http_app(services: Services, webhook_path: str) -> FastAPI:
    app = FastAPI(title="telegram-moderator-bot-api", version="1.0.0")

    def auth(x_admin_token: str = Header(default="")) -> None:
        if services.admin_token and x_admin_token != services.admin_token:
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(webhook_path)
    async def telegram_webhook(request: Request) -> JSONResponse:
        payload = await request.json()
        update = Update.de_json(payload, services.tg_app.bot)
        await services.tg_app.process_update(update)
        return JSONResponse({"ok": True})

    @app.get("/api/v1/status", dependencies=[Depends(auth)])
    async def status() -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.status_summary())

    @app.get("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(auth)])
    async def get_settings(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

    @app.put("/api/v1/chats/{chat_id}/settings", dependencies=[Depends(auth)])
    async def put_settings(chat_id: int, body: dict[str, Any]) -> ApiEnvelope:
        services.repo.update_settings(chat_id, body)
        return ApiEnvelope(ok=True, data=services.repo.get_settings(chat_id).__dict__)

    @app.get("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(auth)])
    async def list_whitelist(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_items("whitelists", chat_id))

    @app.post("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(auth)])
    async def add_whitelist(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        services.repo.add_list_item("whitelists", chat_id, body.get("type", "user"), body["value"])
        return ApiEnvelope(ok=True, data={"created": True})

    @app.delete("/api/v1/chats/{chat_id}/whitelist", dependencies=[Depends(auth)])
    async def delete_whitelist(chat_id: int, value: str, item_type: str = "user") -> ApiEnvelope:
        deleted = services.repo.delete_list_item("whitelists", chat_id, item_type, value)
        return ApiEnvelope(ok=True, data={"deleted": deleted})

    @app.get("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(auth)])
    async def list_blacklist(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_items("blacklists", chat_id))

    @app.post("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(auth)])
    async def add_blacklist(chat_id: int, body: dict[str, str]) -> ApiEnvelope:
        services.repo.add_list_item("blacklists", chat_id, body.get("type", "word"), body["value"])
        return ApiEnvelope(ok=True, data={"created": True})

    @app.delete("/api/v1/chats/{chat_id}/blacklist", dependencies=[Depends(auth)])
    async def delete_blacklist(chat_id: int, value: str, item_type: str = "word") -> ApiEnvelope:
        deleted = services.repo.delete_list_item("blacklists", chat_id, item_type, value)
        return ApiEnvelope(ok=True, data={"deleted": deleted})

    @app.get("/api/v1/chats/{chat_id}/audits", dependencies=[Depends(auth)])
    async def list_audits(chat_id: int, limit: int = 100) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_audits(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/enforcements", dependencies=[Depends(auth)])
    async def list_enforcements(chat_id: int, limit: int = 100) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_enforcements(chat_id, limit))

    @app.get("/api/v1/chats/{chat_id}/appeals", dependencies=[Depends(auth)])
    async def list_appeals(chat_id: int) -> ApiEnvelope:
        return ApiEnvelope(ok=True, data=services.repo.list_appeals(chat_id))

    @app.post("/api/v1/enforcements/{enforcement_id}/rollback", dependencies=[Depends(auth)])
    async def rollback(enforcement_id: int) -> ApiEnvelope:
        data = services.repo.get_enforcement(enforcement_id)
        if not data:
            raise HTTPException(status_code=404, detail="enforcement not found")
        ok, reason = await services.enforcer.rollback(
            services.tg_app.bot,
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

    return app
