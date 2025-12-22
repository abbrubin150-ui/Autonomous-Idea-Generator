"""S2: Type-safety designer (stub)."""\n\nfrom dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass IdeaType:\n    title: str\n    summary: str\n
