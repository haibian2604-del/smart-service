from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_makefile_has_required_targets():
    text = (ROOT / "Makefile").read_text()
    for target in ("db-up", "db-down", "migrate", "seed", "api", "web", "test"):
        assert f"{target}:" in text


def test_runbook_documents_omlx_startup():
    text = (ROOT / "doc" / "RUNBOOK.md").read_text()
    assert "mlx_lm.server" in text
