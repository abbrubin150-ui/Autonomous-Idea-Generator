"""Minimal verification stubs.

In the full spec, this layer would host formal methods (SMT/Coq/Lean/etc.).
Here we implement pragmatic checks:
- EXACT1 (exactly one action) for decision safety
- Policy invariants (fail-closed, audit-required)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str = ""


def verify_exact1(flags: Dict[str, bool], allowed: Optional[List[str]] = None) -> VerificationResult:
    allowed = allowed or list(flags.keys())
    trues = [k for k in allowed if flags.get(k) is True]
    if len(trues) == 1:
        return VerificationResult(ok=True, reason=f"EXACT1 satisfied: {trues[0]}")
    return VerificationResult(ok=False, reason=f"EXACT1 violated: true={trues}")


def verify_policy_invariants(policy: Dict) -> VerificationResult:
    pol = policy.get("policy", {})
    safety = policy.get("safety", {})

    # minimal guardrail: require audit record
    if pol.get("require_audit_record", True) is not True:
        return VerificationResult(ok=False, reason="Policy violation: audit record must be required")

    if pol.get("allow_untrusted_network", False) is not False:
        return VerificationResult(ok=False, reason="Policy violation: untrusted network must be disallowed")

    if pol.get("require_exactly_one_action", True) is not True:
        return VerificationResult(ok=False, reason="Policy violation: EXACT1 must be enforced")

    refuse = safety.get("refuse_categories")
    if not isinstance(refuse, list) or not refuse:
        return VerificationResult(ok=False, reason="Policy violation: safety.refuse_categories must be a non-empty list")

    return VerificationResult(ok=True, reason="Policy invariants OK")
