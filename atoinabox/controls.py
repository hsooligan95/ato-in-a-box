"""The control catalog: what ATO-in-a-Box maps, and what it refuses to.

Two lists, both load-bearing:

- ``MAPPINGS`` — controls this tool will claim *only* when concrete events
  in the store evidence them. Each mapping declares selector groups over
  (source, type) event pairs. A group matches when at least one event
  matches one of its alternatives. Status is ``evidenced`` when every
  group matches, ``partial`` when at least one group matches, and the
  mapping is demoted to the gaps section when nothing matches — no
  artifact, no claim, enforced by construction.

- ``KNOWN_GAPS`` — controls an assessor will ask about that agent-platform
  telemetry of this kind does not evidence. They are declared up front,
  with the reason, instead of being silently omitted. A mapping demoted
  from ``MAPPINGS`` joins this list in the generated pack.

Control summaries are short paraphrases of the control text, written for
this catalog; the interpretation lines are this tool's reading of how the
control applies to an agent platform, and are labeled as interpretation
in the output. Neither is a substitute for the source publications
(NIST SP 800-53 Rev. 5; NIST AI Risk Management Framework 1.0).
"""

from __future__ import annotations

# A selector group: {"label": str, "any_of": [(source, type), ...]}
# source may be "*" to match any producer.

MAPPINGS = [
    {
        "id": "AU-2",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Event Logging",
        "control_summary": "The system generates audit records for defined auditable events.",
        "interpretation": (
            "Every producer in the platform emits structured events into one "
            "append-only store: sessions, tool calls, policy decisions, plan "
            "steps, spans, verdicts."
        ),
        "groups": [
            {"label": "audit events from multiple producers",
             "any_of": [("*", "session_start"), ("*", "tool_executed"),
                        ("*", "step_applied"), ("*", "span")]},
            {"label": "security-relevant events (policy/screening)",
             "any_of": [("*", "policy_decision"), ("*", "screening_findings")]},
        ],
    },
    {
        "id": "AU-3",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Content of Audit Records",
        "control_summary": (
            "Audit records contain what happened, when, where, which subject, "
            "the outcome, and the objects involved."
        ),
        "interpretation": (
            "Every stored event carries timestamp, producer (source), acting "
            "agent, event type, and a shared trace ID; decision records carry "
            "the computed choice and the evidence values that produced it."
        ),
        "groups": [
            {"label": "events carrying the full core field set",
             "any_of": [("*", "*")]},
            {"label": "decision records with computed choice + evidence",
             "any_of": [("*", "decision_record")]},
        ],
        "field_check": ["schema_version", "trace_id", "ts", "source", "agent", "type", "payload"],
    },
    {
        "id": "AU-9",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Protection of Audit Information",
        "control_summary": (
            "Audit information and audit tools are protected from unauthorized "
            "access, modification, and deletion."
        ),
        "interpretation": (
            "The store is a SHA-256 hash chain: rewriting, deleting, or "
            "reordering any historical event breaks the chain at that exact "
            "sequence number, and verification is re-run before any pack is "
            "generated. This evidences tamper *detection*; it does not by "
            "itself evidence access control over the store file (see gaps: "
            "SC-28, AC-3 scope note)."
        ),
        "groups": [
            {"label": "hash-chained audit records across the run",
             "any_of": [("*", "*")]},
        ],
        "requires_chain_ok": True,
    },
    {
        "id": "AC-3",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Access Enforcement",
        "control_summary": (
            "The system enforces approved authorizations for logical access "
            "to information and system resources."
        ),
        "interpretation": (
            "agent-gate evaluates a policy decision for every tool call "
            "(allow / deny / require-approval) before execution; blast-radius "
            "evaluates policy per plan step and required a recorded human "
            "approval before any step executed."
        ),
        "groups": [
            {"label": "per-call policy decisions at the tool gateway",
             "any_of": [("agent-gate", "policy_decision"), ("agent-gate", "decision_record")]},
            {"label": "human approval recorded before destructive execution",
             "any_of": [("blast-radius", "approval_granted")]},
        ],
    },
    {
        "id": "AC-6",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Least Privilege",
        "control_summary": (
            "Only authorized accesses necessary to accomplish assigned tasks "
            "are permitted."
        ),
        "interpretation": (
            "The gateway exposes a per-agent visible tool list (an allowlist) "
            "rather than the upstream's full tool set, and policy decisions "
            "are scoped per agent and per tool."
        ),
        "groups": [
            {"label": "per-agent visible tool allowlist presented at session start",
             "any_of": [("agent-gate", "tools_list")]},
            {"label": "policy decisions scoped to a named agent + tool",
             "any_of": [("agent-gate", "policy_decision")]},
        ],
    },
    {
        "id": "SI-4",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "System Monitoring",
        "control_summary": (
            "The system is monitored to detect attacks and indicators of "
            "potential attacks, including inbound and outbound communications."
        ),
        "interpretation": (
            "Tool results are screened on return for prompt-injection and "
            "exfiltration patterns (and PII patterns) before the agent sees "
            "them; findings are recorded as events and as a computed "
            "decision record."
        ),
        "groups": [
            {"label": "screening findings recorded for returned tool content",
             "any_of": [("agent-gate", "screening_findings")]},
            {"label": "screening outcome recorded as a decision record",
             "any_of": [("agent-gate", "decision_record")]},
        ],
    },
    {
        "id": "CM-3",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Configuration Change Control",
        "control_summary": (
            "Changes to the system are reviewed, tested, and approved (or "
            "disapproved) before implementation."
        ),
        "interpretation": (
            "agent-canary shadow-runs a candidate agent configuration against "
            "the baseline on a golden suite and issues a computed PROMOTE / "
            "BLOCK verdict before the candidate may go live; the verdict and "
            "its reasons are recorded."
        ),
        "groups": [
            {"label": "candidate-vs-baseline evaluation record",
             "any_of": [("agent-canary", "compare_verdict")]},
            {"label": "promotion verdict recorded as a decision record",
             "any_of": [("agent-canary", "decision_record")]},
        ],
    },
    {
        "id": "IR-4",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Incident Handling",
        "control_summary": (
            "An incident handling capability is implemented that includes "
            "preparation, detection, analysis, containment, recovery, and "
            "user response activities."
        ),
        "interpretation": (
            "When post-execution verification failed during the drill, "
            "blast-radius rolled every applied step back and finished in a "
            "recorded rolled_back state — detection (verify checks), "
            "response (rollback), and outcome are all in the record. This "
            "evidences handling of an execution failure, not a full "
            "organizational incident-response program (see gaps)."
        ),
        "groups": [
            {"label": "verification failure detected and recorded",
             "any_of": [("blast-radius", "verify_failed")]},
            {"label": "rollback executed step-by-step",
             "any_of": [("blast-radius", "rollback_step")]},
            {"label": "run closed in a recorded recovery state",
             "any_of": [("blast-radius", "run_finished")]},
        ],
    },
    {
        "id": "CP-4",
        "framework": "NIST SP 800-53 Rev. 5",
        "title": "Contingency Plan Testing",
        "control_summary": (
            "The contingency plan is tested to determine its effectiveness "
            "and readiness to execute."
        ),
        "interpretation": (
            "agent-chaos injects faults (poisoned results, failures) into "
            "agent runs with defenses off and on and records the "
            "silent-failure rate for each mode — a repeatable resilience "
            "test with recorded outcomes."
        ),
        "groups": [
            {"label": "fault-injection scenario results recorded",
             "any_of": [("agent-chaos", "scenario_result")]},
            {"label": "aggregate resilience report recorded",
             "any_of": [("agent-chaos", "chaos_report")]},
        ],
    },
    {
        "id": "GOVERN",
        "framework": "NIST AI RMF 1.0",
        "title": "Governance structures and accountability in the system",
        "control_summary": (
            "Policies, processes, and accountability structures for managing "
            "AI risk are in place and are followed."
        ),
        "interpretation": (
            "Governance here is executable, not documentary: gateway policy "
            "decisions, a recorded human approval gate for destructive "
            "execution, and promotion verdicts are enforced by code and "
            "recorded at decision time. Organizational governance "
            "(charters, roles, risk tolerance statements) is not evidenced "
            "by telemetry — see gaps."
        ),
        "groups": [
            {"label": "policy decisions enforced and recorded",
             "any_of": [("agent-gate", "decision_record"), ("blast-radius", "policy_decision")]},
            {"label": "human approval gate for destructive execution",
             "any_of": [("blast-radius", "approval_granted")]},
        ],
    },
    {
        "id": "MAP",
        "framework": "NIST AI RMF 1.0",
        "title": "Context, risks, and failure modes identified",
        "control_summary": (
            "The context of use is established and risks — including known "
            "failure modes — are identified and characterized."
        ),
        "interpretation": (
            "The chaos scenario catalog enumerates the platform's known "
            "failure modes (poisoned tool results, silent failures) as "
            "named, repeatable scenarios. This is partial MAP evidence: it "
            "characterizes technical failure modes, not the full context / "
            "impact analysis MAP calls for — the pack marks it partial by "
            "construction only if a group fails; the narrative limitation "
            "stands regardless."
        ),
        "groups": [
            {"label": "named failure-mode scenarios enumerated and run",
             "any_of": [("agent-chaos", "scenario_result")]},
        ],
    },
    {
        "id": "MEASURE",
        "framework": "NIST AI RMF 1.0",
        "title": "Quantitative evaluation of the AI system",
        "control_summary": (
            "The AI system is evaluated with quantitative and qualitative "
            "methods; metrics for trustworthiness characteristics are tracked."
        ),
        "interpretation": (
            "Canary compares success rate, accuracy, cost, and latency per "
            "task against thresholds; the ledger attributes cost per span; "
            "the workload's answers are scored for groundedness against a "
            "threshold before being returned."
        ),
        "groups": [
            {"label": "quantitative candidate-vs-baseline metrics",
             "any_of": [("agent-canary", "compare_verdict")]},
            {"label": "per-span cost/performance telemetry",
             "any_of": [("agent-ledger", "span")]},
            {"label": "groundedness scored against a threshold",
             "any_of": [("factory-floor-agent", "groundedness")]},
        ],
    },
    {
        "id": "MANAGE",
        "framework": "NIST AI RMF 1.0",
        "title": "Risks responded to and recovered from",
        "control_summary": (
            "Identified risks are prioritized and acted on; incident "
            "response and recovery plans are executed when events occur."
        ),
        "interpretation": (
            "Responses are recorded actions, not intentions: a promotion "
            "BLOCKed on measured regression, injected content flagged at "
            "the gateway, and a failed execution rolled back to its prior "
            "state."
        ),
        "groups": [
            {"label": "promotion blocked on measured regression",
             "any_of": [("agent-canary", "decision_record")]},
            {"label": "harmful content flagged at the gateway",
             "any_of": [("agent-gate", "decision_record")]},
            {"label": "failed execution rolled back",
             "any_of": [("blast-radius", "run_finished")]},
        ],
    },
]

KNOWN_GAPS = [
    {
        "id": "AC-2", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Account Management",
        "gap": "No account lifecycle evidence exists in the telemetry: agents are identified by name strings in events, with no provisioning, review, or deprovisioning records.",
        "remediation": "Emit identity lifecycle events from the platform's agent registry into the store.",
    },
    {
        "id": "IA-2", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Identification and Authentication",
        "gap": "No authentication events: nothing in the record proves a producer or agent cryptographically is who it claims to be. The hash chain proves records were not altered after the fact, not who wrote them.",
        "remediation": "Sign events at emission (per-producer keys) and record verification in the store.",
    },
    {
        "id": "AU-5", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Response to Audit Logging Process Failures",
        "gap": "No evidence of alerting or fallback behavior when event emission or storage itself fails.",
        "remediation": "Record emission failures and alert on store-append errors; test by fault injection.",
    },
    {
        "id": "AU-11", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Audit Record Retention",
        "gap": "No retention policy or archive artifact: the store is a file with no stated retention period, rotation, or archival record.",
        "remediation": "Adopt and publish a retention schedule; record archival events.",
    },
    {
        "id": "SC-8", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Transmission Confidentiality and Integrity",
        "gap": "No transport evidence (TLS configuration, protected channels) exists in the telemetry; producers write to a local store in this deployment.",
        "remediation": "For networked deployments, record channel configuration and emit connection security events.",
    },
    {
        "id": "SC-12", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Cryptographic Key Establishment and Management",
        "gap": "The chain uses SHA-256 hashing only. No key management artifacts exist because no signing/encryption keys are managed by the platform.",
        "remediation": "If event signing is adopted (see IA-2), document key generation, storage, and rotation.",
    },
    {
        "id": "SC-28", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Protection of Information at Rest",
        "gap": "The store is plaintext JSONL. Payloads are producer audit excerpts; there is no encryption at rest and no redaction stage at capture, so sensitive content in a tool result could persist verbatim.",
        "remediation": "Add a redaction stage at ingestion (the gateway's screening patterns are a starting set) and encrypt archived stores.",
    },
    {
        "id": "CA-2", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Control Assessments",
        "gap": "This pack organizes evidence; it is not an assessment. No assessor determination, control interview, or examination record exists here.",
        "remediation": "An independent assessor reviews this pack against the source publications and records determinations separately.",
    },
    {
        "id": "RA-3", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Risk Assessment",
        "gap": "No formal risk assessment document (threats, likelihoods, organizational impact) is among the artifacts; chaos scenarios characterize technical failure modes only.",
        "remediation": "Produce and version a risk assessment that the scenario catalog references.",
    },
    {
        "id": "AT-2 / PS (family)", "framework": "NIST SP 800-53 Rev. 5",
        "title": "Awareness Training / Personnel Security",
        "gap": "Organizational controls: no training records, role definitions, or personnel artifacts can be evidenced by platform telemetry.",
        "remediation": "Evidence lives in organizational systems; reference it in the SSP, not in this pack.",
    },
    {
        "id": "GOVERN (organizational)", "framework": "NIST AI RMF 1.0",
        "title": "Organizational policies and accountability (GOVERN)",
        "gap": "The pack evidences executable governance (policy in code, approval gates). It does not evidence organizational governance: AI risk policies, accountable roles, or risk-tolerance decisions by named humans.",
        "remediation": "Attach the organization's AI governance charter and decision log as documentary evidence alongside this pack.",
    },
    {
        "id": "MAP (context & impact)", "framework": "NIST AI RMF 1.0",
        "title": "Context of use and impact characterization (MAP)",
        "gap": "Beyond the failure-mode catalog, there is no documented context-of-use analysis, affected-party analysis, or impact characterization among the artifacts.",
        "remediation": "Write and version a MAP document per deployed workload; reference its scenarios from the chaos catalog.",
    },
]
