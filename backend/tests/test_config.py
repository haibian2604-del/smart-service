from app.core.config import Settings


def test_settings_have_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.llm_base_url.endswith("/v1")
    assert s.llm_model == "gemma-4-e2b-it-4bit"
    assert s.refund_amount_threshold == 200


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    s = Settings(_env_file=None)
    assert s.llm_model == "custom-model"
