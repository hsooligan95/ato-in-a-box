"""Fixture store builder: a minimal but valid hash-chained AgentTrace
store exercising every catalog mapping, built with the same chain
algorithm the verifier checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atoinabox.storeio import GENESIS, event_hash  # noqa: E402

TS = "2026-11-21T19:25:00+00:00"


def ev(source, type_, payload, kind="event", agent=None):
    return {
        "schema_version": "1",
        "trace_id": "trace-fixture",
        "ts": TS,
        "source": source,
        "agent": agent or source,
        "type": type_,
        "kind": kind,
        "payload": payload,
    }


def decision(source, point, choice, evidence):
    return ev(source, "decision_record",
              {"decision_point": point, "decider": source, "computed": True,
               "choice": choice, "options": [], "evidence": evidence},
              kind="decision_record")


def fixture_events():
    return [
        ev("agent-canary", "compare_verdict",
           {"base_version": "v1", "candidate_version": "v2-bad", "per_task": [{"task_id": "t01"}]}),
        decision("agent-canary", "agent-canary.compare", "BLOCK",
                 {"reasons": ["success rate dropped 100% -> 36%"]}),
        ev("agent-gate", "session_start", {"agent": "demo-agent", "policyVersion": 1}),
        ev("agent-gate", "tools_list",
           {"agent": "demo-agent", "visibleTools": ["get_cost_summary", "terminate_instance"]}),
        ev("agent-gate", "policy_decision",
           {"tool": "get_cost_summary", "effect": "allow", "stage": "rule", "reason": "Read-only."}),
        decision("agent-gate", "agent-gate.policy", "allow",
                 {"tool": "get_cost_summary", "reason": "Read-only."}),
        ev("agent-gate", "screening_findings",
           {"tool": "get_incident_notes", "findings": [{"pattern": "ignore-instructions"}]}),
        decision("agent-gate", "agent-gate.screening", "flagged",
                 {"patterns": ["ignore-instructions"]}),
        ev("blast-radius", "plan_created", {"result": "ok", "detail": "6 step(s)"}),
        ev("blast-radius", "approval_granted",
           {"approved_by": "operator", "result": "ok", "detail": "plan of 6 step(s)"}),
        ev("blast-radius", "policy_decision", {"event": "step_policy", "result": "ok", "detail": ""}),
        ev("blast-radius", "step_applied", {"result": "ok", "detail": "step 1"}),
        ev("blast-radius", "verify_failed", {"result": "failed", "detail": "8/9 checks passed"}),
        ev("blast-radius", "rollback_step", {"result": "ok", "detail": "step 1 reverted"}),
        ev("blast-radius", "run_finished", {"result": "rolled_back", "detail": "6 step(s) executed"}),
        ev("agent-chaos", "scenario_result",
           {"scenario": "poisoned-result", "mode": "on", "outcome": "success"}),
        ev("agent-chaos", "chaos_report",
           {"headline": {"silent_failure_rate_defenses_off": 1.0,
                         "silent_failure_rate_defenses_on": 0.0, "fault_scenarios": 5}}),
        ev("agent-ledger", "span", {"name": "llm.call"}),
        ev("factory-floor-agent", "groundedness",
           {"grounded": True, "threshold": 0.35, "attempts": 1}),
    ]


def write_store(path: Path, events: list[dict]) -> Path:
    prev = GENESIS
    lines = []
    for i, e in enumerate(events, start=1):
        e = dict(e)
        e["seq"] = i
        e["prev_hash"] = prev
        e["hash"] = event_hash(e)
        prev = e["hash"]
        lines.append(json.dumps(e))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
