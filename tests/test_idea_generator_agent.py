from agents.base_agent import AgentContext
from agents.idea_generator_agent import BaseIdeaProvider, Idea, IdeaGeneratorAgent


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
