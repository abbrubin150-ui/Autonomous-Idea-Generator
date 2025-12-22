from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentContext:
    user_id: str = "anonymous"
    session_id: str = "local"


class BaseAgent:
    name: str = "base"

    def run(self, prompt: str, ctx: AgentContext) -> Dict[str, Any]:
        raise NotImplementedError
