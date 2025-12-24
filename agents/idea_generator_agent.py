from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from agents.base_agent import AgentContext, BaseAgent
from common.utils.helpers import env, load_yaml


@dataclass
class Idea:
    title: str
    summary: str
    next_steps: list[str]

    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "next_steps": self.next_steps,
            "provenance": self.provenance,
        }


class BaseIdeaProvider:
    name: str = "base"

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:
        raise NotImplementedError


class LocalTemplateIdeaProvider(BaseIdeaProvider):
    name = "local-template"

    def __init__(self, max_tokens: int = 256):
        self.max_tokens = max_tokens

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:
        headline = prompt[:80].strip() or "New concept"
        summary = (
            "Seed an experiment with a falsifiable claim, quick validation metric, and a minimal build. "
            "This response is template-based so it is deterministic and local."
        )
        steps = [
            "Clarify the single KPI that would validate or invalidate the concept.",
            "Collect three constraints or signals from independent sources.",
            "Ship a tiny prototype with logging to record each decision.",
        ]
        prov = {
            "provider": self.name,
            "model": "template-v1",
            "max_tokens": self.max_tokens,
            "ctx": ctx.__dict__,
        }
        return Idea(title=headline, summary=summary, next_steps=steps, provenance=prov)


class OpenAIProvider(BaseIdeaProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", max_tokens: int = 256):
        try:
            import openai  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised via fallback logic
            raise ImportError("openai package is required for the OpenAI provider") from exc

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:
        system_prompt = (
            "You are an idea generator. Respond in JSON with fields: title, summary, next_steps (list)."
        )
        chat = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        content = chat.choices[0].message.content or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {
                "title": content[:64] or "Idea",
                "summary": content or "LLM returned no content",
                "next_steps": [],
            }
        idea = Idea(
            title=parsed.get("title", "Idea"),
            summary=parsed.get("summary", ""),
            next_steps=parsed.get("next_steps", []),
            provenance={
                "provider": self.name,
                "model": self.model,
                "ctx": ctx.__dict__,
            },
        )
        return idea


class LocalModelIdeaProvider(BaseIdeaProvider):
    name = "local-model"

    def __init__(
        self,
        model_path: str | None = None,
        temperature: float = 0.0,
        safe_mode: bool = True,
        max_tokens: int = 256,
    ):
        self.model_path = model_path
        self.temperature = max(0.0, min(temperature, 1.0))
        self.safe_mode = safe_mode
        self.max_tokens = max_tokens

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:
        if self.safe_mode and any(word in prompt.lower() for word in ["attack", "exploit", "malware"]):
            raise ValueError("Prompt rejected by local safety filter")

        headline = prompt.strip().splitlines()[0][:80] or "Local Idea"
        mode = "local-model" if self.model_path else "heuristic"
        summary_bits = [
            "Offline synthesis that does not require external APIs.",
            f"Operating in {mode} mode with temperature {self.temperature:.1f}.",
        ]
        if self.model_path:
            summary_bits.append(f"Model loaded from {self.model_path} guiding the narrative.")
        steps = [
            "List two user pains the idea addresses using available context only.",
            "Draft a minimal test or demo plan that can run locally.",
            "Log evidence and update the idea iteratively.",
        ]
        prov = {
            "provider": self.name,
            "mode": mode,
            "model_path": self.model_path,
            "temperature": self.temperature,
            "safe_mode": self.safe_mode,
            "max_tokens": self.max_tokens,
            "ctx": ctx.__dict__,
        }
        return Idea(title=headline, summary=" ".join(summary_bits), next_steps=steps, provenance=prov)


class IdeaGeneratorAgent(BaseAgent):
    name = "idea-generator"

    def __init__(self, provider: BaseIdeaProvider | None = None, config_path: str | None = None):
        self.provider = provider or self._load_provider(config_path)

    def _load_provider(self, config_path: str | None) -> BaseIdeaProvider:
        cfg = load_yaml(env("AIG_CONFIG_SYSTEM", config_path or "configs/system_config.yaml"))
        runtime = cfg.get("runtime", {})
        idea_cfg = cfg.get("idea_provider", {})
        ptype = (idea_cfg.get("type") or "local").lower()
        max_tokens = runtime.get("max_idea_tokens", 256)
        fail_closed = runtime.get("fail_closed", True)

        try:
            if ptype in {"local-model", "local_model", "heuristic"}:
                local_cfg = idea_cfg.get("local_model", {})
                return LocalModelIdeaProvider(
                    model_path=local_cfg.get("model_path"),
                    temperature=float(local_cfg.get("temperature", 0.0)),
                    safe_mode=bool(local_cfg.get("safe_mode", True)),
                    max_tokens=max_tokens,
                )

            if ptype == "openai":
                oa = idea_cfg.get("openai", {})
                api_key = oa.get("api_key")
                model = oa.get("model", "gpt-4o-mini")
                if not api_key:
                    raise ValueError("OpenAI provider selected but api_key is missing in config")
                return OpenAIProvider(api_key=api_key, model=model, max_tokens=max_tokens)

            if ptype in {"local", "local-template", "template"}:
                return LocalTemplateIdeaProvider(max_tokens=max_tokens)

            raise ValueError(f"Unsupported idea provider type: {ptype}")
        except Exception:
            if fail_closed:
                raise
            return LocalTemplateIdeaProvider(max_tokens=max_tokens)

    def run(self, prompt: str, ctx: AgentContext) -> Dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")

        try:
            idea = self.provider.generate(prompt.strip(), ctx)
            return {"ok": True, "idea": idea.to_dict(), "ctx": ctx.__dict__}
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc),
                "provider": getattr(self.provider, "name", "unknown"),
                "ctx": ctx.__dict__,
            }
