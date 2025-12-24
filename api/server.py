from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from agents.base_agent import AgentContext
from agents.supervisor_agent import SupervisorAgent
from api.security import require_api_key, security_responses
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
    log_cfg = sys_cfg.get("system", {}).get("tamper_log", {})
    rotation = log_cfg.get("rotation", {})
    retention = log_cfg.get("retention", {})
    archive_dir = retention.get("archive_dir")
    if archive_dir and not os.path.isabs(archive_dir):
        archive_dir = os.path.join(log_dir, archive_dir)
        retention["archive_dir"] = archive_dir
    if archive_dir:
        ensure_dir(archive_dir)

    tlog = TamperEvidentLog(
        path=f"{log_dir}/tamper_log.jsonl", rotation=rotation, retention=retention
    )
    return SupervisorAgent(policy=pol_cfg, tamper_log=tlog)


SUP = _build_supervisor()


@app.get("/health")
def health():
    return {"ok": True}


@app.post(
    "/generate",
    dependencies=[Depends(require_api_key)],
    responses=security_responses(),
)
def generate(req: GenerateRequest):
    ctx = AgentContext(user_id=req.user_id or "anonymous", session_id=req.session_id or "local")
    return SUP.run(req.prompt, ctx)


@app.get(
    "/audit/verify",
    dependencies=[Depends(require_api_key)],
    responses=security_responses(),
)
def audit_verify():
    # Quick integrity check for the tamper-evident log
    return {"ok": SUP.tamper_log.verify()}
