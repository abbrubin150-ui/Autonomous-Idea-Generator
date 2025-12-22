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
    # minimal guardrail: require audit record
    if policy.get("policy", {}).get("require_audit_record", True) is not True:
        return VerificationResult(ok=False, reason="Policy violation: audit record must be required")
    return VerificationResult(ok=True, reason="Policy invariants OK")
