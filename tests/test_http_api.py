from pathlib import Path

from fastapi.testclient import TestClient

from bot.ai.openai_client import AiVerificationQuestion, AiVerificationQuestionBatchResult, AiWelcomeResult
from bot.api.http_api import Services, create_http_app
from bot.domain.models import AiDecision, ChatRef, MessageRef, ModerationDecision, UserRef
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService, RuntimeConfig
from bot.utils.time import utc_now


class FakeAiModerator:
    def __init__(self, fail_moderation: bool = False, fail_welcome: bool = False) -> None:
        self.fail_moderation = fail_moderation
        self.fail_welcome = fail_welcome

    async def classify(self, message, context):
        if self.fail_moderation:
            raise RuntimeError("moderation boom")
        return AiDecision(
            category="spam",
            level=2,
            confidence=0.93,
            reasons=["test moderation"],
            suggested_action="delete",
            should_escalate_to_admin=False,
            raw={"_model": "fake-moderation-model"},
        )

    async def generate_welcome_result(self, **kwargs):
        if self.fail_welcome:
            raise RuntimeError("welcome boom")
        return AiWelcomeResult(model="fake-welcome-model", text=f"欢迎 {kwargs['user_display_name']} 加入 {kwargs['chat_title']}")

    async def generate_verification_questions_result(self, **kwargs):
        return AiVerificationQuestionBatchResult(
            model="fake-question-model",
            items=[
                AiVerificationQuestion(
                    question="进群后第一件事是什么？",
                    options=["看群规", "发广告", "刷屏"],
                    answer_index=0,
                ),
                AiVerificationQuestion(
                    question="群里交流应保持什么态度？",
                    options=["礼貌友善", "恶意攻击"],
                    answer_index=0,
                ),
            ],
        )


class FakeRuntimeManager:
    def __init__(
        self,
        active: bool = True,
        ai_moderator: FakeAiModerator | None = None,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:
        self.active = active
        self.ai_moderator = ai_moderator or FakeAiModerator()
        self.runtime_config = runtime_config or RuntimeConfig(
            join_welcome_enabled=True,
            join_welcome_use_ai=False,
            join_welcome_template="欢迎 {user} 加入 {chat}",
        )

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
        return self.runtime_config.redacted()

    def get_runtime_config_raw(self) -> RuntimeConfig:
        return self.runtime_config

    def get_ai_moderator(self):
        return self.ai_moderator

    def update_runtime_config(self, payload: dict):
        raise NotImplementedError


def make_app_bundle(
    tmp_path: Path,
    active: bool = True,
    ai_moderator: FakeAiModerator | None = None,
    runtime_config: RuntimeConfig | None = None,
):
    db = Database(tmp_path / "bot.db")
    migrate(db)
    repo = BotRepository(
        db,
        defaults={
            "mode": "balanced",
            "ai_enabled": True,
            "ai_threshold": 0.75,
            "allow_admin_self_test": False,
            "action_policy": "progressive",
            "rate_limit_policy": "default",
            "language": "zh",
            "level3_mute_seconds": 604800,
        },
    )
    runtime_manager = FakeRuntimeManager(active=active, ai_moderator=ai_moderator, runtime_config=runtime_config)
    services = Services(
        repo=repo,
        config_service=ConfigService(db),
        runtime_manager=runtime_manager,
        cors_origins=(),
        web_admin_dist_path=tmp_path / "dist",
    )
    return create_http_app(services, webhook_path="/telegram/webhook"), repo, runtime_manager


def make_app(tmp_path: Path, active: bool = True):
    app, _, _ = make_app_bundle(tmp_path, active=active)
    return app


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


def test_audits_endpoint_exposes_ai_fields(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="测试群"),
        UserRef(user_id=2, username="u", is_bot=False),
    )
    message = MessageRef(chat_id=1, message_id=7, user_id=2, date=utc_now(), text="hello", meta={})
    repo.save_decision(
        message,
        ModerationDecision(
            final_level=1,
            final_action="warn",
            reason_codes=["ai.fallback"],
            rule_results=[],
            ai_used=True,
            ai_decision=None,
            confidence=0.52,
            ai_status="failed",
            ai_error="boom",
        ),
    )
    client = TestClient(app)

    response = client.get("/api/v1/chats/1/audits", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert item["ai_status"] == "failed"
    assert item["ai_error"] == "boom"


def test_moderation_ai_test_endpoint_success(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/chats/1/ai-test/moderation",
        headers={"X-Admin-Token": "admin-token"},
        json={"text": "测试垃圾广告"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["chat_ai_enabled"] is True
    assert data["model"] == "fake-moderation-model"
    assert data["suggested_action"] == "delete"
    assert isinstance(data["latency_ms"], int)


def test_welcome_ai_test_endpoint_failure(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path, ai_moderator=FakeAiModerator(fail_welcome=True))
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/chats/1/ai-test/welcome",
        headers={"X-Admin-Token": "admin-token"},
        json={"user_display_name": "小明"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "ai_test_failed: welcome boom"


def test_ai_test_endpoint_requires_admin_token(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    client = TestClient(app)

    response = client.post("/api/v1/chats/1/ai-test/moderation", headers={"X-Admin-Token": "wrong"}, json={"text": "x"})

    assert response.status_code == 401


def test_verification_question_crud_endpoints(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    client = TestClient(app)

    created = client.post(
        "/api/v1/chats/1/verification/questions",
        headers={"X-Admin-Token": "admin-token"},
        json={
            "scope": "chat",
            "question": "进群后第一件事是什么？",
            "options": ["看群规", "发广告", "刷屏"],
            "answer_index": 0,
        },
    )

    assert created.status_code == 200
    created_data = created.json()["data"]
    assert created_data["scope"] == "chat"
    assert created_data["answer_text"] == "看群规"

    listed = client.get(
        "/api/v1/chats/1/verification/questions",
        headers={"X-Admin-Token": "admin-token"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    updated = client.put(
        f"/api/v1/chats/1/verification/questions/{created_data['id']}",
        headers={"X-Admin-Token": "admin-token"},
        json={
            "scope": "global",
            "question": "本群最重要的规则是什么？",
            "options": ["友善交流", "发广告"],
            "answer_index": 0,
        },
    )
    assert updated.status_code == 200
    updated_data = updated.json()["data"]
    assert updated_data["scope"] == "global"
    assert updated_data["answer_text"] == "友善交流"

    deleted = client.delete(
        f"/api/v1/chats/1/verification/questions/{created_data['id']}",
        headers={"X-Admin-Token": "admin-token"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] == 1


def test_verification_question_generate_endpoint(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/chats/1/verification/questions/generate",
        headers={"X-Admin-Token": "admin-token"},
        json={
            "scope": "chat",
            "count": 2,
            "topic_hint": "群规",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "fake-question-model"
    assert data["count"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["answer_text"] == "看群规"
