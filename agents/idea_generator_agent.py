from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from agents.base_agent import AgentContext, BaseAgent


@dataclass
class Idea:
    title: str
    summary: str
    next_steps: list[str]


class IdeaGeneratorAgent(BaseAgent):
    name = "idea-generator"

    def run(self, prompt: str, ctx: AgentContext) -> Dict[str, Any]:
        # Stub: replace with LLM/heuristics later.
        idea = Idea(
            title=f"רעיון: {prompt[:48].strip() or 'נושא חדש'}",
            summary=(
                "מינימום-גרעין: ניסוח בעיה → הנחת-מבחן → הצעת פתרון → מדד בדיקה. "
                "(כאן זה דמה; חברו לספריית 'פסקה אטומית' בשלב הבא.)"
            ),
            next_steps=[
                "הגדרו מטרת-בדיקה אחת (KPI)",
                "אספו 3 מקורות/אילוצים בלתי-תלויים",
                "צרו אב-טיפוס קטן + לוג Tamper-Evident",
            ],
        )
        return {"idea": idea.__dict__, "ctx": ctx.__dict__}
