"""Load and verify an AgentTrace store.

The verification here is a self-contained re-implementation of the
AgentTrace chain algorithm (SHA-256 over canonical JSON, seq continuity,
prev_hash linkage), matching agent-trace/agenttrace/store.py byte for
byte in behavior. ATO-in-a-Box is a standalone consumer: it must be able
to check the evidence it cites without trusting the producer's own
verifier. If the two implementations ever disagree, that is a finding,
not a rounding error.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

GENESIS = "0" * 64
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1"})


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def event_hash(event_without_hash: dict) -> str:
    return hashlib.sha256(canonical(event_without_hash).encode()).hexdigest()


@dataclass
class VerifyResult:
    ok: bool
    count: int
    broken_seq: int | None = None
    detail: str = ""


class StoreError(ValueError):
    """The store cannot be read as an AgentTrace store at all."""


def load_events(path: str | Path) -> list[dict]:
    """Load every event; fail loudly on malformed lines or schema versions
    this build does not support (an audit tool that silently skips records
    manufactures false confidence)."""
    path = Path(path)
    if not path.exists():
        raise StoreError(f"store not found: {path}")
    events = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StoreError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        version = entry.get("schema_version")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise StoreError(
                f"{path}:{lineno}: unsupported schema_version {version!r}; refusing to read"
            )
        events.append(entry)
    if not events:
        raise StoreError(f"store is empty: {path}")
    return events


def verify_events(events: list[dict]) -> VerifyResult:
    """Verify seq continuity, prev_hash linkage, and every event hash."""
    prev = GENESIS
    for i, entry in enumerate(events, start=1):
        if entry.get("seq") != i:
            return VerifyResult(
                False, len(events), entry.get("seq", i),
                f"seq discontinuity: position {i} holds seq {entry.get('seq')}",
            )
        if entry.get("prev_hash") != prev:
            return VerifyResult(
                False, len(events), entry["seq"],
                "prev_hash does not match the previous event's hash",
            )
        body = {k: v for k, v in entry.items() if k != "hash"}
        if event_hash(body) != entry.get("hash"):
            return VerifyResult(
                False, len(events), entry["seq"],
                "hash mismatch: stored event content was altered",
            )
        prev = entry["hash"]
    return VerifyResult(True, len(events), None, "chain intact end-to-end")


def verify(path: str | Path) -> VerifyResult:
    return verify_events(load_events(path))
