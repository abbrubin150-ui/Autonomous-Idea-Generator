from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from agents.base_agent import AgentContext
from agents.supervisor_agent import SupervisorAgent
from common.logging.tamper_evident_logger import TamperEvidentLog
from common.utils.helpers import env, ensure_dir, load_yaml


class GenerateRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    session_id: str | None = None


app = FastAPI(title="Autonomous Idea Generator", version="0.1.0")


def _build_supervisor() -> SupervisorAgent:
    sys_cfg = load_yaml(env("AIG_CONFIG_SYSTEM", "configs/system_config.yaml"))
    pol_cfg = load_yaml(env("AIG_CONFIG_POLICY", "configs/policy_config.yaml"))

    log_dir = sys_cfg.get("system", {}).get("log_dir", "logs")
    ensure_dir(log_dir)
    tlog = TamperEvidentLog(path=f"{log_dir}/tamper_log.jsonl")
    return SupervisorAgent(policy=pol_cfg, tamper_log=tlog)


SUP = _build_supervisor()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate")
def generate(req: GenerateRequest):
    ctx = AgentContext(user_id=req.user_id or "anonymous", session_id=req.session_id or "local")
    return SUP.run(req.prompt, ctx)


@app.get("/audit/verify")
def audit_verify():
    # Quick integrity check for the tamper-evident log
    return {"ok": SUP.tamper_log.verify()}
