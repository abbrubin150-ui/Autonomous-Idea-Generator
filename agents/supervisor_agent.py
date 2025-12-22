from __future__ import annotations

from typing import Any, Dict

from agents.base_agent import AgentContext, BaseAgent
from agents.idea_generator_agent import IdeaGeneratorAgent
from common.logging.tamper_evident_logger import TamperEvidentLog
from common.verification.formal_verifier import verify_exact1, verify_policy_invariants


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def __init__(self, policy: Dict, tamper_log: TamperEvidentLog):
        self.policy = policy
        self.tamper_log = tamper_log
        self.idea_agent = IdeaGeneratorAgent()

    def run(self, prompt: str, ctx: AgentContext) -> Dict[str, Any]:
        # 1) Policy check
        pol_res = verify_policy_invariants(self.policy)
        if not pol_res.ok:
            self.tamper_log.append("POLICY_BLOCK", {"reason": pol_res.reason, "ctx": ctx.__dict__})
            return {"ok": False, "error": pol_res.reason}

        # 2) EXACT1 decision (minimal): choose exactly one action among {EXECUTE,HOLD,ESCALATE}
        # For starter, always EXECUTE.
        decision = {"EXECUTE": True, "HOLD": False, "ESCALATE": False}
        ex1 = verify_exact1(decision)
        if not ex1.ok:
            self.tamper_log.append("EXACT1_BLOCK", {"reason": ex1.reason, "ctx": ctx.__dict__})
            return {"ok": False, "error": ex1.reason}

        # 3) Generate idea
        out = self.idea_agent.run(prompt, ctx)

        # 4) Audit log
        self.tamper_log.append(
            "IDEA_GENERATED",
            {"prompt": prompt, "decision": decision, "verification": ex1.reason, "ctx": ctx.__dict__},
        )
        return {"ok": True, "result": out, "audit": {"decision": decision, "verification": ex1.reason}}
