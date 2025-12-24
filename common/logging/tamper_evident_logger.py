"""Tamper-evident append-only log (hash chain).

This is a minimal implementation to support S1 'Backup & Tamper-Log Manager'.
"""

"""Tamper-evident append-only log (hash chain) with rotation and retention."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple


def _hash_bytes(b: bytes) -> str:
    return sha256(b).hexdigest()


@dataclass(frozen=True)
class RotationConfig:
    max_bytes: Optional[int] = None
    max_seconds: Optional[float] = None


@dataclass(frozen=True)
class RetentionConfig:
    max_segments: Optional[int] = None
    max_age_seconds: Optional[float] = None
    archive_dir: Optional[str] = None


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

    def __init__(
        self,
        path: str,
        rotation: Optional[Dict[str, Any]] = None,
        retention: Optional[Dict[str, Any]] = None,
    ):
        self.base_path = path
        self._base_dir = os.path.dirname(path) or "."
        os.makedirs(self._base_dir, exist_ok=True)

        root, ext = os.path.splitext(path)
        self._ext = ext or ".log"
        self._root = root if ext else path

        self.rotation = RotationConfig(**(rotation or {}))
        self.retention = RetentionConfig(**(retention or {}))
        self.archive_dir = self.retention.archive_dir
        self._anchor_path = f"{self.base_path}.anchor.json"

        self.current_index = 0
        self._current_segment_started = time.time()
        self._last_hash = "0" * 64

        segments = self._discover_segments()
        if not segments:
            genesis = self._build_entry(event="GENESIS", payload={"v": 1}, prev_hash="0" * 64)
            self._append_raw(genesis, path=self._segment_path(0))
            segments = self._discover_segments()

        active_indices = [idx for idx, _ in segments if self._is_active_segment(idx)]
        self.current_index = max(active_indices) if active_indices else segments[-1][0]
        self._current_segment_started = self._segment_start_time(self._segment_path(self.current_index))
        self._last_hash = self._read_last_hash()

    def _segment_path(self, index: int) -> str:
        if index == 0:
            return self.base_path
        return f"{self._root}-{index:06d}{self._ext}"

    def _segment_regex(self) -> re.Pattern[str]:
        base_name = os.path.basename(self._root)
        ext_pattern = re.escape(self._ext)
        return re.compile(rf"^{re.escape(base_name)}-(\d{{6}}){ext_pattern}$")

    def _append_raw(self, entry: LogEntry, path: Optional[str] = None) -> None:
        path = path or self._segment_path(self.current_index)
        with open(path, "a", encoding="utf-8") as f:
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

    def _segment_start_time(self, path: str) -> float:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line)
                        return float(rec.get("ts", time.time()))
        except FileNotFoundError:
            pass
        return time.time()

    def _read_last_hash(self) -> str:
        segments = self._discover_segments()
        if not segments:
            return "0" * 64
        last_path = segments[-1][1]
        return self._read_segment_last_hash(last_path) or "0" * 64

    def _read_segment_last_hash(self, path: str) -> Optional[str]:
        last = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        last = json.loads(line)
        except FileNotFoundError:
            return None
        if not last:
            return None
        return str(last.get("entry_hash"))

    def _discover_segments(self, include_archive: bool = True) -> List[Tuple[int, str]]:
        segments: Dict[int, str] = {}
        directories: List[str] = [self._base_dir]
        if include_archive and self.archive_dir:
            directories.append(self.archive_dir)

        pattern = self._segment_regex()
        base_filename = os.path.basename(self.base_path)

        for directory in directories:
            if not os.path.isdir(directory):
                continue
            for fname in os.listdir(directory):
                if fname == base_filename:
                    idx = 0
                else:
                    match = pattern.match(fname)
                    if not match:
                        continue
                    idx = int(match.group(1))
                path = os.path.join(directory, fname)
                # Prefer active directory if conflict
                if idx in segments and directory != self._base_dir:
                    continue
                segments[idx] = path

        return sorted(segments.items(), key=lambda x: x[0])

    def _load_anchor(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self._anchor_path):
            return None
        try:
            with open(self._anchor_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_anchor(self, anchor: Dict[str, Any]) -> None:
        with open(self._anchor_path, "w", encoding="utf-8") as f:
            json.dump(anchor, f, ensure_ascii=False, indent=2)

    def _clear_anchor(self) -> None:
        if os.path.exists(self._anchor_path):
            os.remove(self._anchor_path)

    def _apply_retention(self) -> None:
        segments = self._discover_segments(include_archive=False)
        if not segments:
            return

        now = time.time()
        removal: List[Tuple[int, str]] = []

        if self.retention.max_segments is not None and self.retention.max_segments >= 0:
            if len(segments) > self.retention.max_segments:
                removal.extend(segments[: len(segments) - self.retention.max_segments])

        if self.retention.max_age_seconds is not None and self.retention.max_age_seconds >= 0:
            for idx, path in segments:
                try:
                    mtime = os.path.getmtime(path)
                except FileNotFoundError:
                    continue
                if now - mtime > self.retention.max_age_seconds:
                    if (idx, path) not in removal:
                        removal.append((idx, path))

        if not removal:
            if segments and segments[0][0] == 0:
                self._clear_anchor()
            return

        removal = sorted(removal, key=lambda x: x[0])
        removal_set = set(removal)
        keep_indices = {idx for idx, path in segments if (idx, path) not in removal_set}

        anchor_target_idx = min(keep_indices) if keep_indices else None
        if anchor_target_idx is not None and anchor_target_idx > 0 and not self.archive_dir:
            prev_candidates = [idx for idx, _ in removal if idx < anchor_target_idx]
            if prev_candidates:
                prev_idx = max(prev_candidates)
                prev_path = dict(removal).get(prev_idx)
                prev_hash = self._read_segment_last_hash(prev_path) if prev_path else None
                if prev_hash:
                    self._write_anchor(
                        {
                            "next_index": anchor_target_idx,
                            "prev_hash": prev_hash,
                            "ts": time.time(),
                        }
                    )
        else:
            self._clear_anchor()

        if self.archive_dir:
            os.makedirs(self.archive_dir, exist_ok=True)

        for idx, path in removal:
            if self.archive_dir:
                dest = os.path.join(self.archive_dir, os.path.basename(path))
                shutil.move(path, dest)
            else:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    continue

    def _is_active_segment(self, index: int) -> bool:
        return os.path.exists(self._segment_path(index))

    def _rotate_if_needed(self) -> None:
        rotate = False
        current_path = self._segment_path(self.current_index)

        if self.rotation.max_bytes is not None and self.rotation.max_bytes >= 0:
            try:
                if os.path.getsize(current_path) >= self.rotation.max_bytes:
                    rotate = True
            except FileNotFoundError:
                pass

        if self.rotation.max_seconds is not None and self.rotation.max_seconds >= 0:
            if time.time() - self._current_segment_started >= self.rotation.max_seconds:
                rotate = True

        if rotate:
            self.current_index += 1
            self._current_segment_started = time.time()

    def append(self, event: str, payload: Optional[Dict[str, Any]] = None) -> LogEntry:
        payload = payload or {}
        self._rotate_if_needed()

        prev_hash = self._last_hash or self._read_last_hash()
        entry = self._build_entry(event=event, payload=payload, prev_hash=prev_hash)
        self._append_raw(entry)

        self._last_hash = entry.entry_hash
        self._apply_retention()
        return entry

    def verify(self) -> bool:
        segments = self._discover_segments()
        if not segments:
            return False

        anchor = self._load_anchor()
        expected_index = anchor["next_index"] if anchor else 0
        prev_hash = anchor["prev_hash"] if anchor else "0" * 64

        if segments[0][0] != expected_index:
            return False

        for idx, path in segments:
            if idx != expected_index:
                return False
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    body = {
                        "ts": rec["ts"],
                        "event": rec["event"],
                        "payload": rec["payload"],
                        "prev_hash": rec["prev_hash"],
                    }
                    expect = _hash_bytes(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8"))
                    if expect != rec.get("entry_hash"):
                        return False
                    if idx == expected_index and i == 0 and expected_index == 0:
                        if rec.get("prev_hash") != "0" * 64:
                            return False
                    else:
                        if prev_hash is not None and rec.get("prev_hash") != prev_hash:
                            return False
                    prev_hash = rec.get("entry_hash")
            expected_index += 1
        return True

    def tail(self, n: int = 20) -> List[Dict[str, Any]]:
        buf: List[Dict[str, Any]] = []
        segments = self._discover_segments()
        for _, path in segments:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        buf.append(json.loads(line))
        return buf[-n:]
