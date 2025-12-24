from pathlib import Path

from common.logging.tamper_evident_logger import TamperEvidentLog


def _segment_files(log_dir: Path) -> list[str]:
    return sorted([p.name for p in log_dir.iterdir() if p.is_file() and p.suffix == ".jsonl"])


def test_tamper_log_rotates_and_verifies(tmp_path):
    log_path = tmp_path / "log.jsonl"
    log = TamperEvidentLog(str(log_path), rotation={"max_bytes": 1})

    log.append("E1", {"i": 1})
    log.append("E2", {"i": 2})

    segments = _segment_files(tmp_path)
    assert any(name.startswith("log-000001") for name in segments)
    assert log.verify() is True


def test_retention_prunes_and_preserves_anchor(tmp_path):
    log_path = tmp_path / "log.jsonl"
    log = TamperEvidentLog(
        str(log_path), rotation={"max_bytes": 1}, retention={"max_segments": 1}
    )

    log.append("E1", {"i": 1})
    log.append("E2", {"i": 2})

    segments = _segment_files(tmp_path)
    assert len(segments) == 1

    anchor = tmp_path / "log.jsonl.anchor.json"
    assert anchor.exists()
    assert log.verify() is True
