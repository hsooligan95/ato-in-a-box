"""Build an evidence pack from a verified AgentTrace store.

Rules enforced here, structurally:

- The hash chain is re-verified before anything is mapped. A broken
  chain means the pack is refused (CLI default) or stamped BROKEN on
  every surface — never quietly generated.
- A control is claimed only with citations: concrete events (store seq,
  producer, type, timestamp, one-line summary) that exist in the store.
  A mapping whose selectors find nothing is demoted to the gaps section.
- The gaps section always ships, and always includes the declared
  KNOWN_GAPS from the catalog.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .controls import KNOWN_GAPS, MAPPINGS
from .storeio import VerifyResult, load_events, verify, verify_events

MAX_CITATIONS_PER_GROUP = 5


# --------------------------------------------------------------------------
# One-line summaries: pull the deciding values out of each payload so an
# assessor sees *what the artifact says*, not just that it exists.
# --------------------------------------------------------------------------

def summarize(event: dict) -> str:
    p = event.get("payload", {})
    t = event.get("type")
    if t == "decision_record":
        ev = p.get("evidence", {})
        bits = [f"{p.get('decision_point')}: {p.get('choice')}"]
        if ev.get("reasons"):
            bits.append("; ".join(str(r) for r in ev["reasons"]))
        elif ev.get("patterns"):
            bits.append("patterns: " + ", ".join(str(x) for x in ev["patterns"]))
        elif ev.get("tool"):
            bits.append(f"tool={ev['tool']} ({ev.get('reason', '')})".rstrip())
        return " — ".join(bits)[:300]
    if t == "compare_verdict":
        return (f"compare {p.get('base_version')} -> {p.get('candidate_version')}: "
                f"{len(p.get('per_task', []))} tasks evaluated")
    if t == "policy_decision":
        if "effect" in p:
            return f"tool={p.get('tool')} effect={p.get('effect')} stage={p.get('stage')} — {p.get('reason', '')}"[:300]
        return f"event={p.get('event')} result={p.get('result')} — {p.get('detail', '')}"[:300]
    if t == "screening_findings":
        kinds = sorted({f.get("pattern", f.get("kind", "?")) for f in p.get("findings", [])})
        return f"tool={p.get('tool')}: {len(p.get('findings', []))} finding(s): {', '.join(kinds)}"[:300]
    if t == "tools_list":
        return f"agent={p.get('agent')} visible tools: {', '.join(p.get('visibleTools', []))}"[:300]
    if t == "approval_granted":
        return f"approved_by={p.get('approved_by')} — {p.get('detail', '')}"[:300]
    if t in ("verify_failed", "run_finished", "plan_created"):
        return f"result={p.get('result')} — {p.get('detail', '')}"[:300]
    if t == "rollback_step":
        return f"rollback step — {p.get('detail', p.get('result', ''))}"[:300]
    if t == "chaos_report":
        h = p.get("headline", p)
        return (f"silent-failure rate defenses off={h.get('silent_failure_rate_defenses_off')} "
                f"on={h.get('silent_failure_rate_defenses_on')}, "
                f"{h.get('fault_scenarios')} fault scenarios")[:300]
    if t == "scenario_result":
        return (f"scenario={p.get('scenario', p.get('scenario_name', '?'))} "
                f"mode={p.get('mode')} outcome={p.get('outcome')}")[:300]
    if t == "groundedness":
        return f"grounded={p.get('grounded')} threshold={p.get('threshold')} attempts={p.get('attempts')}"[:300]
    if t == "span":
        name = p.get("name") or p.get("attributes", {}).get("name", "span")
        return f"ledger span: {name}"[:300]
    if t == "session_start":
        return f"session start agent={p.get('agent')} policyVersion={p.get('policyVersion')}"[:300]
    return f"{t} from {event.get('source')}"[:300]


def _matches(event: dict, source: str, type_: str) -> bool:
    return (source == "*" or event.get("source") == source) and (
        type_ == "*" or event.get("type") == type_
    )


def _cite(event: dict) -> dict:
    return {
        "seq": event["seq"],
        "source": event.get("source"),
        "type": event.get("type"),
        "ts": event.get("ts"),
        "summary": summarize(event),
    }


def evaluate_mapping(mapping: dict, events: list[dict], chain_ok: bool) -> dict:
    """Resolve one catalog mapping against the store.

    Returns a control entry with status evidenced / partial / gap.
    Citations are real events from the store — nothing else can appear.
    """
    groups_out = []
    matched_groups = 0
    for group in mapping["groups"]:
        hits = [e for e in events
                if any(_matches(e, s, t) for s, t in group["any_of"])]
        if hits:
            matched_groups += 1
        groups_out.append({
            "label": group["label"],
            "match_count": len(hits),
            "citations": [_cite(e) for e in hits[:MAX_CITATIONS_PER_GROUP]],
        })
    if mapping.get("requires_chain_ok") and not chain_ok:
        status = "gap"
    elif matched_groups == len(mapping["groups"]):
        status = "evidenced"
    elif matched_groups > 0:
        status = "partial"
    else:
        status = "gap"
    entry = {
        "id": mapping["id"],
        "framework": mapping["framework"],
        "title": mapping["title"],
        "status": status,
        "control_summary": mapping["control_summary"],
        "interpretation": mapping["interpretation"],
        "evidence_groups": groups_out,
    }
    if mapping.get("field_check"):
        fields = mapping["field_check"]
        complete = sum(1 for e in events if all(f in e for f in fields))
        entry["field_check"] = {
            "fields": fields,
            "events_with_all_fields": complete,
            "events_total": len(events),
        }
        if complete < len(events):
            entry["status"] = "partial" if status == "evidenced" else status
    return entry


# --------------------------------------------------------------------------
# Continuous checks: computable claims about this store, pass/fail.
# --------------------------------------------------------------------------

def run_checks(events: list[dict], chain: VerifyResult) -> list[dict]:
    checks = []
    checks.append({
        "id": "chain-integrity",
        "claim": "The audit hash chain is intact end-to-end.",
        "result": "pass" if chain.ok else "fail",
        "detail": (f"{chain.count} events verified" if chain.ok
                   else f"chain broken at seq {chain.broken_seq}: {chain.detail}"),
    })
    approvals = [e["seq"] for e in events
                 if e.get("source") == "blast-radius" and e.get("type") == "approval_granted"]
    applied = [e["seq"] for e in events
               if e.get("source") == "blast-radius" and e.get("type") == "step_applied"]
    if approvals and applied:
        ok = min(approvals) < min(applied)
        checks.append({
            "id": "approval-precedes-execution",
            "claim": "A human approval was recorded before any destructive step executed.",
            "result": "pass" if ok else "fail",
            "detail": f"approval at seq {min(approvals)}; first step_applied at seq {min(applied)}",
        })
    else:
        checks.append({
            "id": "approval-precedes-execution",
            "claim": "A human approval was recorded before any destructive step executed.",
            "result": "not-observed",
            "detail": "store lacks an approval or an executed step to compare",
        })
    screening = [e for e in events if e.get("type") == "screening_findings"]
    checks.append({
        "id": "screening-active",
        "claim": "Tool-result screening ran at the gateway during the recorded run.",
        "result": "pass" if screening else "fail",
        "detail": f"{len(screening)} screening_findings event(s) in store",
    })
    decisions = [e for e in events if e.get("kind") == "decision_record"]
    computed = [e for e in decisions if e.get("payload", {}).get("computed") is True]
    checks.append({
        "id": "decision-records-computed",
        "claim": "Every decision record was emitted by the code branch that computed the decision.",
        "result": "pass" if decisions and len(computed) == len(decisions) else "fail",
        "detail": f"{len(computed)}/{len(decisions)} decision records carry computed=true",
    })
    return checks


# --------------------------------------------------------------------------
# Pack assembly
# --------------------------------------------------------------------------

def build_pack(store_path: str | Path, *, tamper_note: dict | None = None) -> tuple[dict, VerifyResult]:
    events = load_events(store_path)
    chain = verify_events(events)
    controls = [evaluate_mapping(m, events, chain.ok) for m in MAPPINGS]
    evidenced = [c for c in controls if c["status"] in ("evidenced", "partial")]
    demoted = [c for c in controls if c["status"] == "gap"]
    gaps = [
        {"id": c["id"], "framework": c["framework"], "title": c["title"],
         "gap": "No artifact in this store evidences this control: none of its "
                "evidence selectors matched an event.",
         "remediation": "Produce the missing telemetry/artifacts, or scope the "
                        "control out with an assessor-agreed rationale."}
        for c in demoted
    ] + [dict(g) for g in KNOWN_GAPS]
    pack = {
        "pack_version": "1",
        "tool": {"name": "ato-in-a-box", "version": __version__},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integrity": {
            "status": "VERIFIED" if chain.ok else "BROKEN",
            "events_verified": chain.count,
            "broken_seq": chain.broken_seq,
            "detail": chain.detail,
        },
        "source_store": {
            "path": str(store_path),
            "events": len(events),
            "trace_ids": sorted({e.get("trace_id") for e in events}),
            "producers": sorted({e.get("source") for e in events}),
        },
        "checks": run_checks(events, chain),
        "controls": evidenced,
        "gaps": gaps,
        "summary": {
            "evidenced": sum(1 for c in evidenced if c["status"] == "evidenced"),
            "partial": sum(1 for c in evidenced if c["status"] == "partial"),
            "gaps": len(gaps),
        },
        "disclaimer": (
            "This pack organizes machine-generated evidence from an agent "
            "platform's audit store. It is evidence organization, not a "
            "compliance certification, not an assessor determination, and "
            "not an Authorization to Operate. Control summaries are "
            "paraphrases; interpretations are labeled as such. Authority "
            "rests with the source publications and the assessing body."
        ),
    }
    if tamper_note:
        pack["tamper_demonstration"] = tamper_note
    return pack, chain


def find_tamper_demonstration(store_path: str | Path) -> dict | None:
    """If a `<stem>.tampered.jsonl` sibling exists (the drill ships one),
    verify it and record the demonstrated detection as AU-9 evidence."""
    p = Path(store_path)
    sibling = p.with_name(p.stem + ".tampered.jsonl")
    if not sibling.exists():
        return None
    result = verify(sibling)
    return {
        "artifact": sibling.name,
        "chain_ok": result.ok,
        "broken_seq": result.broken_seq,
        "detail": result.detail,
        "meaning": ("A deliberately altered copy of the store fails "
                    "verification at the exact altered sequence — the "
                    "tamper-detection property AU-9 relies on, demonstrated "
                    "on a real artifact rather than asserted."),
    }


# --------------------------------------------------------------------------
# Assessor document (Markdown)
# --------------------------------------------------------------------------

def render_markdown(pack: dict) -> str:
    integ = pack["integrity"]
    lines = []
    lines.append("# Agent Platform — Compliance Evidence Pack")
    lines.append("")
    if integ["status"] != "VERIFIED":
        lines.append(f"> ## ⚠ INTEGRITY: BROKEN — chain fails at seq {integ['broken_seq']}. "
                     "This pack is stamped, not certified: do not rely on its citations.")
        lines.append("")
    lines.append(f"**Integrity:** {integ['status']} — {integ['events_verified']} events re-verified "
                 f"before generation ({integ['detail']}).")
    lines.append(f"**Source store:** `{pack['source_store']['path']}` · "
                 f"traces: {', '.join(pack['source_store']['trace_ids'])} · "
                 f"producers: {', '.join(pack['source_store']['producers'])}")
    lines.append(f"**Generated:** {pack['generated_at']} by ato-in-a-box {pack['tool']['version']}")
    lines.append("")
    lines.append(f"> {pack['disclaimer']}")
    lines.append("")
    s = pack["summary"]
    lines.append(f"**Coverage:** {s['evidenced']} controls evidenced · {s['partial']} partial · "
                 f"{s['gaps']} gaps (POA&M-style, §3).")
    lines.append("")
    lines.append("## 1. Continuous checks")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("|---|---|---|")
    for c in pack["checks"]:
        lines.append(f"| {c['id']} — {c['claim']} | **{c['result']}** | {c['detail']} |")
    lines.append("")
    if pack.get("tamper_demonstration"):
        td = pack["tamper_demonstration"]
        lines.append(f"**Tamper demonstration:** `{td['artifact']}` fails verification at "
                     f"seq {td['broken_seq']} ({td['detail']}). {td['meaning']}")
        lines.append("")
    lines.append("## 2. Control evidence matrix")
    lines.append("")
    for c in pack["controls"]:
        lines.append(f"### {c['id']} — {c['title']}  ·  {c['framework']}  ·  **{c['status'].upper()}**")
        lines.append("")
        lines.append(f"*Control (paraphrase):* {c['control_summary']}")
        lines.append("")
        lines.append(f"*Interpretation for this platform:* {c['interpretation']}")
        lines.append("")
        if c.get("field_check"):
            fc = c["field_check"]
            lines.append(f"Field check: {fc['events_with_all_fields']}/{fc['events_total']} events "
                         f"carry all of {', '.join(fc['fields'])}.")
            lines.append("")
        for g in c["evidence_groups"]:
            lines.append(f"- **{g['label']}** — {g['match_count']} matching event(s):")
            for cit in g["citations"]:
                lines.append(f"  - seq {cit['seq']} · {cit['source']}/{cit['type']} · {cit['ts']} — {cit['summary']}")
        lines.append("")
    lines.append("## 3. Gaps — POA&M-style")
    lines.append("")
    lines.append("Controls the evidence does **not** cover. Absence here is a finding, "
                 "not an oversight: no artifact, no claim.")
    lines.append("")
    lines.append("| Control | Framework | Gap | Suggested remediation |")
    lines.append("|---|---|---|---|")
    for g in pack["gaps"]:
        lines.append(f"| {g['id']} — {g['title']} | {g['framework']} | {g['gap']} | {g['remediation']} |")
    lines.append("")
    return "\n".join(lines)


def write_pack(pack: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "evidence-pack.json"
    md_path = out / "evidence-pack.md"
    json_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(pack), encoding="utf-8")
    return json_path, md_path
