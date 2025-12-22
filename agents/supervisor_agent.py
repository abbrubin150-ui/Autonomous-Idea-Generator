from __future__ import annotations

import re
from typing import Any, Dict, List

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
        self.allowed_actions = self.policy.get("policy", {}).get(
            "allowed_actions", ["EXECUTE", "HOLD", "ESCALATE"]
        )
        if not self.allowed_actions:
            self.allowed_actions = ["EXECUTE"]
        default_action = self.policy.get("policy", {}).get("default_action")
        self.default_action = (
            default_action if default_action in self.allowed_actions else self.allowed_actions[0]
        )

    def run(self, prompt: str, ctx: AgentContext) -> Dict[str, Any]:
        # 1) Policy check
        pol_res = verify_policy_invariants(self.policy)
        if not pol_res.ok:
            self.tamper_log.append("POLICY_BLOCK", {"reason": pol_res.reason, "ctx": ctx.__dict__})
            return {"ok": False, "error": pol_res.reason}

        refusal_reason = self._prompt_refused(prompt)
        if refusal_reason:
            self.tamper_log.append(
                "POLICY_BLOCK", {"reason": refusal_reason, "ctx": ctx.__dict__, "prompt": prompt}
            )
            return {"ok": False, "error": refusal_reason}

        # 2) EXACT1 decision (minimal): choose exactly one action among {EXECUTE,HOLD,ESCALATE}
        # For starter, choose configured default action.
        decision = {act: False for act in self.allowed_actions}
        decision[self.default_action] = True
        if self.policy.get("policy", {}).get("require_exactly_one_action", True):
            ex1 = verify_exact1(decision, allowed=self.allowed_actions)
            if not ex1.ok:
                self.tamper_log.append("EXACT1_BLOCK", {"reason": ex1.reason, "ctx": ctx.__dict__})
                return {"ok": False, "error": ex1.reason}
            verification_reason = ex1.reason
        else:
            verification_reason = "EXACT1 not required by policy"

        # 3) Generate idea
        out = self.idea_agent.run(prompt, ctx)

        # 4) Audit log
        self.tamper_log.append(
            "IDEA_GENERATED",
            {
                "prompt": prompt,
                "decision": decision,
                "verification": verification_reason,
                "ctx": ctx.__dict__,
            },
        )
        return {
            "ok": True,
            "result": out,
            "audit": {"decision": decision, "verification": verification_reason},
        }

    def _prompt_refused(self, prompt: str) -> str | None:
        prompt_lc = prompt.lower()
        for pattern in self._refuse_categories():
            if not isinstance(pattern, str):
                continue
            if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2:
                try:
                    if re.search(pattern[1:-1], prompt, flags=re.IGNORECASE | re.MULTILINE):
                        return f"Prompt matches refused category regex: {pattern}"
                except re.error:
                    continue
            else:
                keyword = pattern.lower()
                if keyword in prompt_lc or keyword.replace("_", " ") in prompt_lc:
                    return f"Prompt contains refused category keyword: {pattern}"
        return None

    def _refuse_categories(self) -> List[str]:
        safety = self.policy.get("safety", {})
        refuse = safety.get("refuse_categories", [])
        return refuse if isinstance(refuse, list) else []
