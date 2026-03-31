from pathlib import Path

from fastapi.testclient import TestClient

from bot.api.http_api import Services, create_http_app
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService


class FakeRuntimeManager:
    def __init__(self, active: bool = True) -> None:
        self.active = active

    def is_active(self) -> bool:
        return self.active

    def runtime_state(self) -> dict:
        return {
            "state": "active" if self.active else "setup",
            "config_complete": self.active,
            "config_version": 1,
            "run_mode": "polling",
        }

    def verify_admin_token(self, token: str) -> bool:
        return token == "admin-token"

    def get_runtime_config_public(self) -> dict:
        return {}

    def update_runtime_config(self, payload: dict):
        raise NotImplementedError


def make_app(tmp_path: Path, active: bool = True):
    db = Database(tmp_path / "bot.db")
    migrate(db)
    repo = BotRepository(
        db,
        defaults={
            "mode": "balanced",
            "ai_enabled": True,
            "ai_threshold": 0.75,
            "action_policy": "progressive",
            "rate_limit_policy": "default",
            "language": "zh",
            "level3_mute_seconds": 604800,
        },
    )
    services = Services(
        repo=repo,
        config_service=ConfigService(db),
        runtime_manager=FakeRuntimeManager(active=active),
        cors_origins=(),
        web_admin_dist_path=tmp_path / "dist",
    )
    return create_http_app(services, webhook_path="/telegram/webhook")


def test_runtime_state_exposes_backend_version(tmp_path):
    client = TestClient(make_app(tmp_path))

    response = client.get("/api/v1/runtime/state")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["state"] == "active"
    assert isinstance(payload["backend_version"], str)
    assert payload["backend_version"]


def test_auth_login_validates_admin_token(tmp_path):
    client = TestClient(make_app(tmp_path))

    ok = client.post("/api/v1/auth/login", json={"admin_token": "admin-token"})
    assert ok.status_code == 200
    assert ok.json()["data"]["authenticated"] is True

    bad = client.post("/api/v1/auth/login", json={"admin_token": "wrong"})
    assert bad.status_code == 401
