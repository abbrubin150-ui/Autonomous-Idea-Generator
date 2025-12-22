from common.logging.tamper_evident_logger import TamperEvidentLog
from common.verification.formal_verifier import verify_exact1


def test_exact1_ok():
    res = verify_exact1({"A": True, "B": False, "C": False})
    assert res.ok


def test_exact1_fail():
    res = verify_exact1({"A": True, "B": True, "C": False})
    assert not res.ok


def test_tamper_log_chain(tmp_path):
    p = tmp_path / "log.jsonl"
    t = TamperEvidentLog(str(p))
    t.append("X", {"a": 1})
    t.append("Y", {"b": 2})
    assert t.verify() is True
