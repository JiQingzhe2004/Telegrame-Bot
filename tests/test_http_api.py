from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
        self._tg_app = SimpleNamespace(
            bot=SimpleNamespace(
                get_me=AsyncMock(return_value=SimpleNamespace(id=999)),
                get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member", until_date=None))
            )
        )
        self.sync_bot_commands = AsyncMock()

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

    def get_bot_application(self):
        return self._tg_app

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
            "chat_enabled": False,
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


def test_admin_members_endpoint_exposes_current_status(tmp_path):
    app, repo, runtime_manager = make_app_bundle(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="测试群"),
        UserRef(user_id=2, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.save_admin_action(1, "ban_member", "applied", target={"user_id": 2}, user_id=2)
    runtime_manager._tg_app.bot.get_chat_member = AsyncMock(
        return_value=SimpleNamespace(
            status="restricted",
            until_date=None,
            user=SimpleNamespace(id=2, username="alice", is_bot=False, full_name="Alice"),
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/chats/1/admin/members", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["user_id"] == 2
    assert row["current_status"] == "restricted"
    assert row["current_status_until_date"] is None
    assert row["is_bot"] is False
    assert row["is_whitelisted"] is False


def test_admin_kick_member_endpoint(tmp_path):
    app, repo, runtime_manager = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    runtime_manager._tg_app.bot.get_chat_member = AsyncMock(
        side_effect=[
            SimpleNamespace(
                status="administrator",
                can_change_info=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_promote_members=True,
                can_manage_video_chats=True,
                can_manage_chat=True,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                is_anonymous=False,
            ),
            SimpleNamespace(
                status="member",
                user=SimpleNamespace(id=2, username="alice", is_bot=False, full_name="Alice"),
            ),
        ]
    )
    runtime_manager._tg_app.bot.ban_chat_member = AsyncMock(return_value=True)
    runtime_manager._tg_app.bot.unban_chat_member = AsyncMock(return_value=True)
    client = TestClient(app)

    response = client.post("/api/v1/chats/1/admin/members/2/kick", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["applied"] is True
    assert data["permission_ok"] is True


def test_admin_ban_member_endpoint_rejects_protected_bot_target(tmp_path):
    app, repo, runtime_manager = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="测试群"))
    runtime_manager._tg_app.bot.get_chat_member = AsyncMock(
        side_effect=[
            SimpleNamespace(
                status="administrator",
                can_change_info=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_promote_members=True,
                can_manage_video_chats=True,
                can_manage_chat=True,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                is_anonymous=False,
            ),
            SimpleNamespace(
                status="member",
                user=SimpleNamespace(id=2, username="helper_bot", is_bot=True, full_name="Helper Bot"),
            ),
        ]
    )
    runtime_manager._tg_app.bot.ban_chat_member = AsyncMock(return_value=True)
    client = TestClient(app)

    response = client.post("/api/v1/chats/1/admin/members/2/ban", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["applied"] is False
    assert data["action_supported"] is False
    assert data["reason"] == "protected_target_bot"


def test_points_endpoints(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="积分群"),
        UserRef(user_id=2, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="积分群"))
    client = TestClient(app)

    config = client.get("/api/v1/chats/1/points/config", headers={"X-Admin-Token": "admin-token"})
    assert config.status_code == 200
    assert config.json()["data"]["points_enabled"] is True

    updated = client.put(
        "/api/v1/chats/1/points/config",
        headers={"X-Admin-Token": "admin-token"},
        json={"points_message_reward": 3, "points_daily_cap": 12},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["points_message_reward"] == 3

    adjusted = client.post(
        "/api/v1/chats/1/points/adjust",
        headers={"X-Admin-Token": "admin-token"},
        json={"user_id": 2, "amount": 8, "reason": "seed"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["balance_after"] == 8

    balance = client.get("/api/v1/chats/1/points/balance/2", headers={"X-Admin-Token": "admin-token"})
    assert balance.status_code == 200
    assert balance.json()["data"]["balance"] == 8

    leaderboard = client.get("/api/v1/chats/1/points/leaderboard", headers={"X-Admin-Token": "admin-token"})
    assert leaderboard.status_code == 200
    assert leaderboard.json()["data"][0]["user_id"] == 2

    ledger = client.get("/api/v1/chats/1/points/ledger", headers={"X-Admin-Token": "admin-token"})
    assert ledger.status_code == 200
    assert ledger.json()["data"][0]["event_type"] == "admin_adjust"


def test_points_redemption_status_endpoint(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="积分群"))
    redemption = repo.save_redemption(
        chat_id=1,
        user_id=2,
        item_id=3,
        price_points=10,
        status="pending",
        reward_payload='{"title":"积分榜之星"}',
        expires_at=None,
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/chats/1/points/redemptions/{redemption['id']}/status",
        headers={"X-Admin-Token": "admin-token"},
        json={"status": "active"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_title_redemption_activation_applies_title(tmp_path):
    app, repo, runtime_manager = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="积分群"))
    from bot.points_service import PointsService

    service = PointsService(repo)
    service.update_shop(
        chat_id=1,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请头衔",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": None,
                "enabled": True,
                "meta": {"title_mode": "fixed", "fixed_title": "积分榜之星", "auto_approve": False},
            }
        ],
    )
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")
    redemption = service.redeem(chat_id=1, user_id=2, item_key="leaderboard_title")["redemption"]
    runtime_manager._tg_app.bot.get_me = AsyncMock(return_value=SimpleNamespace(id=999))
    runtime_manager._tg_app.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="creator", is_anonymous=False))
    runtime_manager._tg_app.bot.set_chat_administrator_custom_title = AsyncMock(return_value=True)
    client = TestClient(app)

    response = client.post(
        f"/api/v1/chats/1/points/redemptions/{redemption['id']}/status",
        headers={"X-Admin-Token": "admin-token"},
        json={"status": "active"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"
    runtime_manager._tg_app.bot.set_chat_administrator_custom_title.assert_awaited_once_with(
        chat_id=1,
        user_id=2,
        custom_title="积分榜之星",
    )


def test_points_pool_adjust_endpoint(tmp_path):
    app, repo, _ = make_app_bundle(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="积分群"))
    repo.add_pool_ledger(chat_id=1, change_amount=30, event_type="packet_expired_to_pool", operator="system", reason="seed")
    client = TestClient(app)

    added = client.post(
        "/api/v1/chats/1/points/pool/adjust",
        headers={"X-Admin-Token": "admin-token"},
        json={"amount": 20, "reason": "manual add"},
    )
    assert added.status_code == 200
    assert added.json()["data"]["balance_after"] == 50

    deducted = client.post(
        "/api/v1/chats/1/points/pool/adjust",
        headers={"X-Admin-Token": "admin-token"},
        json={"amount": -10, "reason": "manual sub"},
    )
    assert deducted.status_code == 200
    assert deducted.json()["data"]["balance_after"] == 40


def test_sync_telegram_commands_endpoint(tmp_path):
    app, _, runtime_manager = make_app_bundle(tmp_path)
    client = TestClient(app)

    response = client.post("/api/v1/runtime/telegram/commands/sync", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    assert response.json()["data"]["synced"] is True
    runtime_manager.sync_bot_commands.assert_awaited_once()
