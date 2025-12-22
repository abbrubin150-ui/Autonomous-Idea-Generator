# Autonomous Idea Generator (S1–S9) — Starter Repo

This repository scaffolds the **Autonomous Idea Generator** described in the nine-layer specification (S1–S9).

## What you get (v0.1.0)
- A minimal FastAPI service (`/generate`) that returns a **stub idea** + an **audit record**.
- A **tamper-evident append-only log** (hash chain) stored in `logs/tamper_log.jsonl`.
- A simple **EXACT1** verifier to enforce “exactly one action” decisions.
- Layered folders (`S1_...` → `S9_...`) with stubs per-role, ready to be implemented.

## Quickstart (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload
```

Then:
```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/generate \
  -H 'content-type: application/json' \
  -d '{"prompt":"חדשנות בחינוך עם Offline-first"}'
curl -s http://localhost:8000/audit/verify
```

## Quickstart (Docker)
```bash
docker compose up --build
```

## Where to extend next
1. Replace `IdeaGeneratorAgent` with a real generator (LLM / heuristic engine).
2. Add policy gates (S4/S7) before execution.
3. Add model registry + dataset versioning (S3 + DVC).
4. Expand audit proofs (S2 ∴Auditor) and formal checks.

## License
MIT
