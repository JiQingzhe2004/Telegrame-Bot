import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import Chat
from telegram.error import TelegramError

from bot.domain.models import ChatRef, ModerationDecision, UserRef
from bot.domain.moderation import PermissionSnapshot
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.adapter_ptb import (
    _register_bot_commands,
    on_points_self_callback,
    VERIFY_CALLBACK_PREFIX,
    _verification_timeout,
    on_group_message,
    on_join_verify_callback,
    on_new_chat_members,
)
from bot.telegram.commands import (
    HONGBAO_CALLBACK_PREFIX,
    USER_FLOW_CALLBACK_PREFIX,
    hongbao_cmd,
    on_hongbao_callback,
    on_private_text,
    on_user_flow_callback,
    pay_cmd,
    points_cmd,
    rank_cmd,
    start_cmd,
    status_cmd,
)
from bot.utils.time import utc_now


def make_repo(tmp_path) -> BotRepository:
    db = Database(tmp_path / "bot.db")
    migrate(db)
    return BotRepository(
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


def test_new_chat_members_registers_chat_when_bot_itself_is_added(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100123, type=Chat.SUPERGROUP, title="测试群"),
        effective_message=SimpleNamespace(
            new_chat_members=[
                SimpleNamespace(
                    id=999001,
                    is_bot=True,
                    username="test_bot",
                    first_name="Test",
                    last_name="Bot",
                    full_name="Test Bot",
                )
            ]
        ),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )

    asyncio.run(on_new_chat_members(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100123 for chat in chats)


def test_group_message_from_admin_still_registers_chat(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100456, type=Chat.SUPERGROUP, title="管理群"),
        effective_user=SimpleNamespace(id=42, is_bot=False, username="owner", first_name="Owner", last_name=None),
        effective_message=SimpleNamespace(text="hello", caption=None),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": object(),
                "enforcer": object(),
            }
        ),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=True)):
        asyncio.run(on_group_message(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100456 for chat in chats)


def test_group_message_ignores_disabled_chat(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100457, type=Chat.SUPERGROUP, title="未开放群"))
    service = SimpleNamespace(decide=AsyncMock())
    enforcer = SimpleNamespace(apply=AsyncMock())
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100457, type=Chat.SUPERGROUP, title="未开放群"),
        effective_user=SimpleNamespace(id=42, is_bot=False, username="member", first_name="Member", last_name=None),
        effective_message=SimpleNamespace(text="hello", caption=None),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "moderation_service": service, "enforcer": enforcer}),
        bot=SimpleNamespace(),
    )

    asyncio.run(on_group_message(update, context))

    assert service.decide.await_count == 0
    assert enforcer.apply.await_count == 0


def test_admin_command_registers_chat_before_permission_check(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100789, type=Chat.SUPERGROUP, title="命令群"),
        effective_user=SimpleNamespace(id=7, is_bot=False),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.commands.is_admin", new=AsyncMock(return_value=False)):
        asyncio.run(status_cmd(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100789 for chat in chats)


def test_group_message_calls_decide_and_can_reach_ai_flow(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100990, type=Chat.SUPERGROUP, title="AI群"))
    repo.update_settings(-100990, {"chat_enabled": True})
    service = SimpleNamespace(
        decide=AsyncMock(
            return_value=ModerationDecision(
                final_level=0,
                final_action="none",
                reason_codes=["ok"],
                rule_results=[],
                ai_used=False,
                ai_decision=None,
                confidence=0.5,
                duration_seconds=None,
            )
        )
    )
    enforcer = SimpleNamespace(
        apply=AsyncMock(return_value=SimpleNamespace(applied_action="none")),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100990, type=Chat.SUPERGROUP, title="AI群"),
        effective_user=SimpleNamespace(id=1234, is_bot=False, username="member", first_name="Member", last_name=None),
        effective_message=SimpleNamespace(text="测试消息", caption=None, message_id=55, date=utc_now()),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": service,
                "enforcer": enforcer,
            }
        ),
        bot=SimpleNamespace(),
    )

    permission_snapshot = AsyncMock(return_value=PermissionSnapshot(False, False, False))
    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=False)), patch(
        "bot.telegram.adapter_ptb.get_permission_snapshot",
        new=permission_snapshot,
    ):
        asyncio.run(on_group_message(update, context))

    assert service.decide.await_count == 1
    assert enforcer.apply.await_count == 1
    permission_snapshot.assert_awaited_once_with(context.bot, -100990)
    members = repo.list_chat_members(-100990)
    assert len(members) == 1
    assert members[0]["user_id"] == 1234
    audits = repo.list_audits(-100990)
    assert len(audits) == 1
    assert audits[0]["user_id"] == 1234


def test_admin_self_test_runs_audit_but_skips_enforcement(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100991, type=Chat.SUPERGROUP, title="自测群"))
    repo.update_settings(-100991, {"chat_enabled": True, "allow_admin_self_test": True})
    service = SimpleNamespace(
        decide=AsyncMock(
            return_value=ModerationDecision(
                final_level=2,
                final_action="delete",
                reason_codes=["ai.other"],
                rule_results=[],
                ai_used=True,
                ai_decision=None,
                confidence=0.91,
                duration_seconds=None,
            )
        )
    )
    enforcer = SimpleNamespace(apply=AsyncMock())
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100991, type=Chat.SUPERGROUP, title="自测群"),
        effective_user=SimpleNamespace(id=42, is_bot=False, username="owner", first_name="Owner", last_name=None),
        effective_message=SimpleNamespace(text="测试自测", caption=None, message_id=56, date=utc_now(), reply_text=reply_text),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": service,
                "enforcer": enforcer,
            }
        ),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=True)):
        asyncio.run(on_group_message(update, context))

    assert service.decide.await_count == 1
    assert enforcer.apply.await_count == 0
    reply_text.assert_awaited_once()
    audits = repo.list_audits(-100991)
    assert len(audits) == 1
    assert audits[0]["final_level"] == 2


def test_join_verify_pass_cleans_up_messages_and_sends_welcome(tmp_path):
    repo = make_repo(tmp_path)
    query = SimpleNamespace(
        data=f"{VERIFY_CALLBACK_PREFIX}-100123:42:ok",
        from_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        answer=AsyncMock(),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "runtime_config": SimpleNamespace(
                    join_verification_max_attempts=3,
                    join_welcome_enabled=True,
                    join_welcome_use_ai=False,
                ),
                "pending_join_verifications": {
                    "-100123:42": {
                        "verify_message_id": 200,
                        "join_message_id": 100,
                        "attempts": 0,
                        "question_type": "button",
                        "display_name": "Alice",
                    }
                },
                "ai_moderator": None,
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            restrict_chat_member=AsyncMock(),
            delete_message=AsyncMock(),
            send_message=AsyncMock(),
        ),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=-100123, title="测试群", type="supergroup"),
    )

    with patch("bot.telegram.adapter_ptb._build_welcome_text", new=AsyncMock(return_value="欢迎 Alice")):
        asyncio.run(on_join_verify_callback(update, context))

    query.answer.assert_awaited_once()
    assert context.application.bot_data["pending_join_verifications"] == {}
    assert context.bot.delete_message.await_count == 2
    context.bot.send_message.assert_awaited_once_with(chat_id=-100123, text="欢迎 Alice")


def test_join_verify_timeout_cleans_up_and_kicks_member(tmp_path):
    repo = make_repo(tmp_path)
    context = SimpleNamespace(
        job=SimpleNamespace(data={"chat_id": -100124, "user_id": 43}),
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "pending_join_verifications": {
                    "-100124:43": {
                        "verify_message_id": 201,
                        "join_message_id": 101,
                        "attempts": 1,
                        "display_name": "Bob",
                    }
                },
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            delete_message=AsyncMock(),
            ban_chat_member=AsyncMock(),
            unban_chat_member=AsyncMock(),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=301)),
        ),
    )

    asyncio.run(_verification_timeout(context))

    assert context.application.bot_data["pending_join_verifications"] == {}
    assert context.bot.delete_message.await_count == 2
    context.bot.ban_chat_member.assert_awaited_once()
    context.bot.unban_chat_member.assert_awaited_once()
    context.bot.send_message.assert_awaited_once_with(chat_id=-100124, text="Bob 未在限时内完成入群验证，已被移出群聊。")


def test_new_chat_members_skips_verification_setup_when_restrict_fails(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100125, type=Chat.SUPERGROUP, title="验证群"))
    repo.update_settings(-100125, {"chat_enabled": True})
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100125, type=Chat.SUPERGROUP, title="验证群"),
        effective_message=SimpleNamespace(
            message_id=88,
            new_chat_members=[
                SimpleNamespace(
                    id=44,
                    is_bot=False,
                    username="bob",
                    first_name="Bob",
                    last_name=None,
                    full_name="Bob",
                )
            ],
            reply_text=AsyncMock(),
        ),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "runtime_config": SimpleNamespace(
                    join_verification_enabled=True,
                    join_verification_timeout_seconds=180,
                    join_verification_max_attempts=3,
                    join_verification_question_type="button",
                    join_verification_whitelist_bypass=True,
                    join_welcome_enabled=False,
                ),
                "pending_join_verifications": {},
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            restrict_chat_member=AsyncMock(side_effect=TelegramError("telegram forbid")),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=302)),
        ),
    )

    asyncio.run(on_new_chat_members(update, context))

    assert context.application.bot_data["pending_join_verifications"] == {}
    context.bot.send_message.assert_awaited_once_with(
        chat_id=-100125,
        text="Bob 的入群验证未生效：机器人无法限制新成员发言，请检查管理员权限。",
    )


def test_points_cmd_sends_private_balance_instead_of_group_balance(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100200, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.adjust_points(chat_id=-100200, user_id=42, amount=8, event_type="admin_adjust", operator="test")
    group_reply = AsyncMock()
    bot = SimpleNamespace(send_message=AsyncMock(), delete_message=AsyncMock(), username="test_bot")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100200, type=Chat.SUPERGROUP, title="积分群"),
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_message=SimpleNamespace(message_id=88, reply_text=group_reply),
        message=SimpleNamespace(message_id=88, reply_text=group_reply),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=bot,
    )

    asyncio.run(points_cmd(update, context))

    bot.send_message.assert_awaited_once()
    args = bot.send_message.await_args.kwargs
    assert args["chat_id"] == 42
    assert "当前余额：8" in args["text"]
    group_reply.assert_awaited_once()
    assert "积分明细已私聊发送" in group_reply.await_args.args[0]
    bot.delete_message.assert_awaited_once_with(chat_id=-100200, message_id=88)


def test_points_self_callback_only_allows_self(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100201, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.adjust_points(chat_id=-100201, user_id=42, amount=5, event_type="admin_adjust", operator="test")
    query = SimpleNamespace(
        data="points:self:-100201:42",
        from_user=SimpleNamespace(id=43),
        answer=AsyncMock(),
    )
    bot = SimpleNamespace(send_message=AsyncMock(), username="test_bot")
    update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=-100201, title="积分群"))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"repo": repo}), bot=bot)

    asyncio.run(on_points_self_callback(update, context))

    query.answer.assert_awaited_once()
    assert "只能查看你自己的积分" in query.answer.await_args.args[0]
    assert bot.send_message.await_count == 0


def test_rank_cmd_attaches_private_points_button(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100202, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.adjust_points(chat_id=-100202, user_id=42, amount=6, event_type="admin_adjust", operator="test")
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100202, type=Chat.SUPERGROUP, title="积分群"),
        effective_user=SimpleNamespace(id=42, username="alice"),
        message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"repo": repo}), bot=SimpleNamespace())

    asyncio.run(rank_cmd(update, context))

    reply_text.assert_awaited_once()
    assert reply_text.await_args.kwargs["reply_markup"] is not None


def test_register_bot_commands_sets_private_group_and_admin_scopes():
    bot = SimpleNamespace(set_my_commands=AsyncMock())
    app = SimpleNamespace(bot=bot)

    asyncio.run(_register_bot_commands(app))

    assert bot.set_my_commands.await_count == 3
    group_commands = bot.set_my_commands.await_args_list[1].args[0]
    assert any(command.command == "checkin" for command in group_commands)
    assert any(command.command == "tasks" for command in group_commands)
    assert any(command.command == "shop" for command in group_commands)
    assert any(command.command == "redeem" for command in group_commands)


def test_pay_cmd_sends_private_notice_to_recipient(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100203, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.upsert_chat_user(
        ChatRef(chat_id=-100203, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=43, username="bob", is_bot=False, first_name="Bob"),
    )
    repo.adjust_points(chat_id=-100203, user_id=42, amount=10, event_type="admin_adjust", operator="test")
    reply_text = AsyncMock()
    bot = SimpleNamespace(send_message=AsyncMock(), delete_message=AsyncMock())
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100203, type=Chat.SUPERGROUP, title="积分群"),
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_message=SimpleNamespace(message_id=77, reply_text=reply_text),
        message=SimpleNamespace(message_id=77, reply_text=reply_text),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=bot,
        args=["43", "3"],
    )

    asyncio.run(pay_cmd(update, context))

    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.kwargs["chat_id"] == 43
    assert "积分到账通知" in bot.send_message.await_args.kwargs["text"]
    assert "到账积分：3" in bot.send_message.await_args.kwargs["text"]
    bot.delete_message.assert_awaited_once_with(chat_id=-100203, message_id=77)


def test_points_cmd_private_chat_no_longer_loops_back_to_group(tmp_path):
    repo = make_repo(tmp_path)
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
        effective_user=SimpleNamespace(id=42, username="alice"),
        message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"repo": repo}), bot=SimpleNamespace(username="test_bot"))

    asyncio.run(points_cmd(update, context))

    reply_text.assert_awaited_once()
    assert "这里是机器人私聊窗口" in reply_text.await_args.args[0]


def test_points_cmd_group_failure_includes_private_link_button(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100204, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    reply_text = AsyncMock()
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=TelegramError("private blocked")), username="test_bot")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100204, type=Chat.SUPERGROUP, title="积分群"),
        effective_user=SimpleNamespace(id=42, username="alice"),
        message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"repo": repo}), bot=bot)

    asyncio.run(points_cmd(update, context))

    reply_text.assert_awaited_once()
    assert "请先手动打开机器人私聊窗口并发送 /start" in reply_text.await_args.args[0]


def test_start_cmd_in_private_renders_home_menu(tmp_path):
    repo = make_repo(tmp_path)
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=SimpleNamespace(username="test_bot"),
        args=[],
    )

    asyncio.run(start_cmd(update, context))

    reply_text.assert_awaited_once()
    assert "个人中心" in reply_text.await_args.args[0]
    assert reply_text.await_args.kwargs["reply_markup"] is not None


def test_user_flow_shop_redeem_via_callbacks(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100300, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    repo.adjust_points(chat_id=-100300, user_id=42, amount=50, event_type="admin_adjust", operator="test")
    query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}shop:item:-100300:leaderboard_title",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "user_sessions": {"42": {"recent_chat_id": -100300, "recent_chat_title": "积分群"}}}),
        bot=SimpleNamespace(username="test_bot"),
    )

    asyncio.run(on_user_flow_callback(update, context))

    query.answer.assert_awaited_once()
    assert "商品详情" in query.edit_message_text.await_args.kwargs["text"]

    redeem_query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}shop:redeem:-100300:leaderboard_title",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    redeem_update = SimpleNamespace(
        callback_query=redeem_query,
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )

    asyncio.run(on_user_flow_callback(redeem_update, context))

    assert "兑换成功" in redeem_query.edit_message_text.await_args.kwargs["text"]
    balance = repo.get_points_balance(-100300, 42)
    assert balance["balance"] == 20


def test_user_flow_title_redeem_auto_apply_fixed_title(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat_user(
        ChatRef(chat_id=-100301, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    from bot.points_service import PointsService

    PointsService(repo).update_shop(
        chat_id=-100301,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请头衔",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": None,
                "enabled": True,
                "meta": {"title_mode": "fixed", "fixed_title": "积分榜之星", "auto_approve": True},
            }
        ],
    )
    repo.adjust_points(chat_id=-100301, user_id=42, amount=50, event_type="admin_adjust", operator="test")
    redeem_query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}shop:redeem:-100301:leaderboard_title",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    redeem_update = SimpleNamespace(
        callback_query=redeem_query,
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "user_sessions": {"42": {"recent_chat_id": -100301, "recent_chat_title": "积分群"}}}),
        bot=SimpleNamespace(
            username="test_bot",
            get_me=AsyncMock(return_value=SimpleNamespace(id=999)),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="creator", is_anonymous=False)),
            set_chat_administrator_custom_title=AsyncMock(),
        ),
    )

    asyncio.run(on_user_flow_callback(redeem_update, context))

    context.bot.set_chat_administrator_custom_title.assert_awaited_once_with(chat_id=-100301, user_id=42, custom_title="积分榜之星")
    assert "头衔已自动设置为" in redeem_query.edit_message_text.await_args.kwargs["text"]


def test_private_text_submits_custom_title_and_auto_applies(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100302, type=Chat.SUPERGROUP, title="积分群"))
    repo.upsert_chat_user(
        ChatRef(chat_id=-100302, type=Chat.SUPERGROUP, title="积分群"),
        UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"),
    )
    from bot.points_service import PointsService

    service = PointsService(repo)
    service.update_shop(
        chat_id=-100302,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请头衔",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": None,
                "enabled": True,
                "meta": {"title_mode": "custom", "fixed_title": "积分榜之星", "auto_approve": True},
            }
        ],
    )
    repo.adjust_points(chat_id=-100302, user_id=42, amount=50, event_type="admin_adjust", operator="test")
    redemption = service.redeem(chat_id=-100302, user_id=42, item_key="leaderboard_title")["redemption"]

    private_reply = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_message=SimpleNamespace(text="自定义头衔"),
        message=SimpleNamespace(reply_text=private_reply),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "user_sessions": {"42": {"recent_chat_id": -100302, "recent_chat_title": "积分群", "pending_custom_title": {"redemption_id": redemption["id"], "chat_id": -100302}}},
            }
        ),
        bot=SimpleNamespace(
            username="test_bot",
            get_me=AsyncMock(return_value=SimpleNamespace(id=999)),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="creator", is_anonymous=False)),
            set_chat_administrator_custom_title=AsyncMock(),
        ),
    )

    asyncio.run(on_private_text(update, context))

    context.bot.set_chat_administrator_custom_title.assert_awaited_once_with(chat_id=-100302, user_id=42, custom_title="自定义头衔")
    assert "自动生效" in private_reply.await_args.args[0]


def test_private_transfer_flow_completes_with_callbacks_and_text(tmp_path):
    repo = make_repo(tmp_path)
    chat_ref = ChatRef(chat_id=-100301, type=Chat.SUPERGROUP, title="积分群")
    repo.upsert_chat_user(chat_ref, UserRef(user_id=42, username="alice", is_bot=False, first_name="Alice"))
    repo.upsert_chat_user(chat_ref, UserRef(user_id=43, username="bob", is_bot=False, first_name="Bob"))
    repo.adjust_points(chat_id=-100301, user_id=42, amount=30, event_type="admin_adjust", operator="test")
    bot = SimpleNamespace(send_message=AsyncMock(), username="test_bot")
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "user_sessions": {"42": {"recent_chat_id": -100301, "recent_chat_title": "积分群"}}}),
        bot=bot,
    )

    start_query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}pay:start:-100301",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    start_update = SimpleNamespace(
        callback_query=start_query,
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )
    asyncio.run(on_user_flow_callback(start_update, context))
    assert "转账积分" in start_query.edit_message_text.await_args.kwargs["text"]

    private_reply = AsyncMock()
    text_update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_message=SimpleNamespace(text="43"),
        message=SimpleNamespace(reply_text=private_reply),
    )
    asyncio.run(on_private_text(text_update, context))

    amount_query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}pay:amount:-100301:5",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    amount_update = SimpleNamespace(
        callback_query=amount_query,
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )
    asyncio.run(on_user_flow_callback(amount_update, context))
    assert "确认转账" in amount_query.edit_message_text.await_args.kwargs["text"]

    confirm_query = SimpleNamespace(
        data=f"{USER_FLOW_CALLBACK_PREFIX}pay:confirm:-100301:43:5",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    confirm_update = SimpleNamespace(
        callback_query=confirm_query,
        effective_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        effective_chat=SimpleNamespace(id=42, type=Chat.PRIVATE, title=None),
    )
    asyncio.run(on_user_flow_callback(confirm_update, context))

    assert "转账成功" in confirm_query.edit_message_text.await_args.kwargs["text"]
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.kwargs["chat_id"] == 43
    assert repo.get_points_balance(-100301, 42)["balance"] == 25
    assert repo.get_points_balance(-100301, 43)["balance"] == 5


def test_hongbao_callback_uses_prompt_owner_mapping(tmp_path):
    repo = make_repo(tmp_path)
    prompt_reply = AsyncMock(return_value=SimpleNamespace(message_id=501))
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100400, type=Chat.SUPERGROUP, title="积分群"),
        effective_user=SimpleNamespace(id=42, username="alice"),
        effective_message=SimpleNamespace(reply_text=prompt_reply),
        message=SimpleNamespace(message_id=300, reply_text=prompt_reply),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"repo": repo}), bot=SimpleNamespace(delete_message=AsyncMock()))

    asyncio.run(hongbao_cmd(update, context))

    query = SimpleNamespace(
        data=f"{HONGBAO_CALLBACK_PREFIX}create:-100400:random",
        from_user=SimpleNamespace(id=42),
        message=SimpleNamespace(message_id=501),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    callback_update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=-100400, type=Chat.SUPERGROUP, title="积分群"))

    asyncio.run(on_hongbao_callback(callback_update, context))

    assert context.application.bot_data["user_sessions"]["42"]["hongbao"]["split_mode"] == "random"
    query.edit_message_text.assert_awaited_once()
