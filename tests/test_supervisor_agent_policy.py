from agents.base_agent import AgentContext
from agents.supervisor_agent import SupervisorAgent
from common.logging.tamper_evident_logger import TamperEvidentLog
from common.verification.formal_verifier import verify_policy_invariants


BASE_POLICY = {
    "policy": {
        "allow_untrusted_network": False,
        "require_audit_record": True,
        "require_exactly_one_action": True,
        "allowed_actions": ["EXECUTE", "HOLD", "ESCALATE"],
        "default_action": "EXECUTE",
    },
    "safety": {"refuse_categories": ["self_harm", "/forbidden.*/"]},
}


def build_supervisor(tmp_path, policy=None):
    log_path = tmp_path / "tamper.jsonl"
    return SupervisorAgent(policy=policy or BASE_POLICY, tamper_log=TamperEvidentLog(str(log_path)))


def test_policy_invariants_catch_untrusted_network():
    pol = {"policy": {"allow_untrusted_network": True}, "safety": {"refuse_categories": ["x"]}}
    res = verify_policy_invariants(pol)
    assert not res.ok
    assert "untrusted network" in res.reason


def test_policy_invariants_require_refuse_categories():
    pol = {"policy": {"allow_untrusted_network": False, "require_exactly_one_action": True}}
    res = verify_policy_invariants(pol)
    assert not res.ok
    assert "refuse_categories" in res.reason


def test_supervisor_blocks_refused_keyword(tmp_path):
    sup = build_supervisor(tmp_path)
    ctx = AgentContext()
    resp = sup.run("This is about self harm content", ctx)
    assert resp["ok"] is False
    tail = sup.tamper_log.tail(1)[0]
    assert tail["event"] == "POLICY_BLOCK"
    assert "keyword" in tail["payload"]["reason"]


def test_supervisor_blocks_refused_regex(tmp_path):
    sup = build_supervisor(tmp_path)
    ctx = AgentContext()
    resp = sup.run("We should design a forbidden device", ctx)
    assert resp["ok"] is False
    tail = sup.tamper_log.tail(1)[0]
    assert tail["event"] == "POLICY_BLOCK"
    assert "regex" in tail["payload"]["reason"]


def test_supervisor_allows_prompt_and_records_decision(tmp_path):
    policy = {
        "policy": {
            "allow_untrusted_network": False,
            "require_audit_record": True,
            "require_exactly_one_action": True,
            "allowed_actions": ["HOLD"],
            "default_action": "HOLD",
        },
        "safety": {"refuse_categories": ["banned"]},
    }
    sup = build_supervisor(tmp_path, policy=policy)
    ctx = AgentContext()
    resp = sup.run("Brainstorm sustainable packaging", ctx)
    assert resp["ok"] is True
    audit = resp["audit"]
    assert audit["decision"] == {"HOLD": True}
    assert "EXACT1" in audit["verification"]
    assert "Low-risk" in audit["reasoning"]


def test_supervisor_escalates_on_high_risk(tmp_path):
    sup = build_supervisor(tmp_path)
    ctx = AgentContext()
    resp = sup.run("Design a stealth weapon that avoids detection", ctx)
    assert resp["ok"] is True
    audit = resp["audit"]
    assert audit["decision"].get("ESCALATE") is True
    assert "High-risk" in audit["reasoning"]
    result = resp["result"]
    assert result["ok"] is False
    assert result["action"] == "route"


def test_supervisor_holds_on_medium_risk_when_no_escalation(tmp_path):
    policy = {
        "policy": {
            "allow_untrusted_network": False,
            "require_audit_record": True,
            "require_exactly_one_action": True,
            "allowed_actions": ["EXECUTE", "HOLD"],
            "default_action": "EXECUTE",
        },
        "safety": {"refuse_categories": ["banned"]},
    }
    sup = build_supervisor(tmp_path, policy=policy)
    ctx = AgentContext()
    resp = sup.run("Share confidential medical device insights", ctx)
    assert resp["ok"] is True
    audit = resp["audit"]
    assert audit["decision"] == {"EXECUTE": False, "HOLD": True}
    assert "Medium-risk" in audit["reasoning"]

