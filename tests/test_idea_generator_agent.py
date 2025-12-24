from agents.base_agent import AgentContext
from agents.idea_generator_agent import (
    BaseIdeaProvider,
    Idea,
    IdeaGeneratorAgent,
    LocalModelIdeaProvider,
    LocalTemplateIdeaProvider,
)


class FakeProvider(BaseIdeaProvider):
    name = "fake"

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:
        return Idea(
            title=f"Idea about {prompt}",
            summary="A concise concept.",
            next_steps=["one", "two"],
            provenance={"provider": self.name, "ctx": ctx.__dict__},
        )


class FailingProvider(BaseIdeaProvider):
    name = "failing"

    def generate(self, prompt: str, ctx: AgentContext) -> Idea:  # pragma: no cover - intentionally fails
        raise RuntimeError("provider boom")


def test_run_happy_path():
    ctx = AgentContext(user_id="u1", session_id="s1")
    agent = IdeaGeneratorAgent(provider=FakeProvider())
    res = agent.run("test prompt", ctx)

    assert res["ok"] is True
    assert res["idea"]["title"] == "Idea about test prompt"
    assert res["idea"]["provenance"]["provider"] == "fake"


def test_malformed_prompt():
    ctx = AgentContext()
    agent = IdeaGeneratorAgent(provider=FakeProvider())

    for bad in ["", "   ", None]:
        try:
            agent.run(bad, ctx)
        except ValueError:
            continue
        raise AssertionError("Expected ValueError for malformed prompt")


def test_provider_failure():
    ctx = AgentContext()
    agent = IdeaGeneratorAgent(provider=FailingProvider())

    res = agent.run("prompt", ctx)
    assert res["ok"] is False
    assert "boom" in res["error"]
    assert res["provider"] == "failing"


def test_local_model_provider_success():
    ctx = AgentContext(user_id="local-user", session_id="local-session")
    agent = IdeaGeneratorAgent(
        provider=LocalModelIdeaProvider(
            model_path="/models/offline.bin",
            temperature=0.2,
            safe_mode=False,
            max_tokens=128,
        )
    )

    res = agent.run("ship a personal knowledge base", ctx)

    assert res["ok"] is True
    assert res["idea"]["provenance"]["provider"] == "local-model"
    assert res["idea"]["provenance"]["mode"] == "local-model"
    assert "/models/offline.bin" in res["idea"]["summary"]


def test_local_model_provider_safety_rejection():
    ctx = AgentContext()
    agent = IdeaGeneratorAgent(provider=LocalModelIdeaProvider(safe_mode=True))

    res = agent.run("plan a malware attack", ctx)

    assert res["ok"] is False
    assert "safety filter" in res["error"]
    assert res["provider"] == "local-model"


def test_load_provider_fallback_when_openai_misconfigured(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
runtime:
  fail_closed: false
  max_idea_tokens: 64
idea_provider:
  type: openai
  openai:
    model: gpt-4o-mini
        """
    )

    agent = IdeaGeneratorAgent(config_path=str(cfg))

    assert isinstance(agent.provider, LocalTemplateIdeaProvider)
