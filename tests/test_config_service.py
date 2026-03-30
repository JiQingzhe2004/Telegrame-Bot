from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.system_config import ConfigService


def make_service(tmp_path):
    db = Database(tmp_path / "bot.db")
    migrate(db)
    return ConfigService(db)


def test_config_service_save_and_read(tmp_path):
    svc = make_service(tmp_path)
    out = svc.save_runtime_config(
        {
            "bot_token": "token-abc",
            "admin_api_token": "admin-xyz",
            "run_mode": "polling",
        }
    )
    got = svc.get_runtime_config()
    assert out.bot_token == "token-abc"
    assert got.admin_api_token == ""
    assert bool(got.admin_api_token_hash) is True
    assert svc.verify_admin_token("admin-xyz") is True
    assert svc.is_complete(got) is True


def test_config_service_bootstrap_code_once(tmp_path):
    svc = make_service(tmp_path)
    code = svc.issue_bootstrap_code()
    assert svc.verify_bootstrap_code(code) is True
    assert svc.verify_bootstrap_code(code) is False


def test_config_service_setup_token(tmp_path):
    svc = make_service(tmp_path)
    token = svc.issue_setup_token()
    assert svc.verify_setup_token(token, consume=False) is True
    assert svc.verify_setup_token(token, consume=True) is True
    assert svc.verify_setup_token(token, consume=False) is False


def test_activation_validation_requires_required_fields(tmp_path):
    svc = make_service(tmp_path)
    errs = svc.validate_activation()
    assert "bot_token is required" in errs
    assert "admin_api_token is required" in errs


def test_admin_token_is_hashed_and_verifiable(tmp_path):
    svc = make_service(tmp_path)
    cfg = svc.save_runtime_config(
        {
            "bot_token": "bot-token",
            "admin_api_token": "my-admin-token",
        }
    )
    assert cfg.admin_api_token == ""
    assert cfg.admin_api_token_hash
    assert svc.verify_admin_token("my-admin-token") is True
    assert svc.verify_admin_token("wrong-token") is False
