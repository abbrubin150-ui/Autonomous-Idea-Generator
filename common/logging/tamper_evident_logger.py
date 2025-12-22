"""Tamper-evident append-only log (hash chain).

This is a minimal implementation to support S1 'Backup & Tamper-Log Manager'.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, List, Optional


def _hash_bytes(b: bytes) -> str:
    return sha256(b).hexdigest()


@dataclass(frozen=True)
class LogEntry:
    ts: float
    event: str
    payload: Dict[str, Any]
    prev_hash: str
    entry_hash: str


class TamperEvidentLog:
    """Hash-chained log stored as JSONL.

    Each line is an entry that includes prev_hash and entry_hash.
    Any mutation breaks the chain.
    """

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            # genesis record
            genesis = self._build_entry(event="GENESIS", payload={"v": 1}, prev_hash="0" * 64)
            self._append_raw(genesis)

    def _append_raw(self, entry: LogEntry) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")

    def _build_entry(self, event: str, payload: Dict[str, Any], prev_hash: str) -> LogEntry:
        ts = time.time()
        body = {
            "ts": ts,
            "event": event,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        entry_hash = _hash_bytes(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        return LogEntry(ts=ts, event=event, payload=payload, prev_hash=prev_hash, entry_hash=entry_hash)

    def _read_last_hash(self) -> str:
        last = None
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)
        if not last:
            return "0" * 64
        return str(last["entry_hash"])

    def append(self, event: str, payload: Optional[Dict[str, Any]] = None) -> LogEntry:
        payload = payload or {}
        prev_hash = self._read_last_hash()
        entry = self._build_entry(event=event, payload=payload, prev_hash=prev_hash)
        self._append_raw(entry)
        return entry

    def verify(self) -> bool:
        prev_hash = None
        with open(self.path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                rec = json.loads(line)
                # recompute hash
                body = {
                    "ts": rec["ts"],
                    "event": rec["event"],
                    "payload": rec["payload"],
                    "prev_hash": rec["prev_hash"],
                }
                expect = _hash_bytes(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8"))
                if expect != rec.get("entry_hash"):
                    return False
                if i == 0:
                    # genesis must point to 0..0
                    if rec.get("prev_hash") != "0" * 64:
                        return False
                else:
                    if prev_hash is not None and rec.get("prev_hash") != prev_hash:
                        return False
                prev_hash = rec.get("entry_hash")
        return True

    def tail(self, n: int = 20) -> List[Dict[str, Any]]:
        buf: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    buf.append(json.loads(line))
        return buf[-n:]
