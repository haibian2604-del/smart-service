from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_config_points_to_metadata():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert len(script.get_heads()) <= 1  # 空仓库或单 head，不允许分叉
