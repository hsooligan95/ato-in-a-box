# ATO-in-a-Box

**Turn an agent platform's audit trail into the evidence pack an assessor actually asks for.**

Point it at an [AgentTrace](https://github.com/hsooligan95/agent-trace) store and it produces a structured compliance evidence pack: platform controls mapped to **NIST SP 800-53 Rev. 5** controls and **NIST AI RMF** functions, where *every* mapped control cites the concrete artifact that evidences it — event sequence numbers, the hash-chain verification result, gateway policy decision records, canary promotion verdicts — plus an explicit **gaps section** listing the controls the evidence does *not* cover, POA&M-style.

The rule the whole tool is built around: **no artifact, no claim.** A mapping whose evidence selectors match nothing in the store is not printed as coverage — it is demoted to the gaps section, automatically.

```bash
python -m atoinabox build \
  --store ../agent-trace/drill/output/trace-drill-45d404d0/store.jsonl \
  --out examples
# pack written: examples/evidence-pack.json + examples/evidence-pack.md
# integrity: VERIFIED (117 events) · evidenced: 13 · partial: 0 · gaps: 12
```

Outputs: `evidence-pack.json` (machine-readable) and `evidence-pack.md` (the human-readable assessor document). The committed pack under [`examples/`](examples/) was generated from the AgentTrace phase-2 proof drill — a real 117-event run across six producers (canary, gate, blast-radius, factory-floor, ledger, chaos) under one trace ID.

## Verify before you trust

The hash chain is **re-verified before anything is mapped**, with a self-contained re-implementation of the AgentTrace chain algorithm (the consumer must not have to trust the producer's own verifier). If the chain is broken:

- default: the build is **refused** (exit 2, nothing written);
- `--allow-broken`: a pack is generated, stamped **INTEGRITY: BROKEN** in the JSON, at the top of the Markdown, and in the CLI output — and AU-9, whose claim rests on the chain, is demoted to the gaps section.

If a `store.tampered.jsonl` sibling sits next to the store (the drill ships one), the pack verifies it too and records the demonstrated detection — the drill's tampered copy fails at exactly seq 8 — as evidence rather than assertion.

## What the drill's pack claims — and what it doesn't

Excerpt from the generated pack (citations are real events from the drill store):

> ### CM-3 — Configuration Change Control · NIST SP 800-53 Rev. 5 · **EVIDENCED**
> - **promotion verdict recorded as a decision record** — 1 matching event(s):
>   - seq 2 · agent-canary/decision_record — agent-canary.compare: BLOCK — success rate dropped 100% -> 36% (drop 0.64 > allowed 0.05); candidate committed 10 forbidden action(s)
>
> ### SI-4 — System Monitoring · **EVIDENCED**
>   - seq 8 · agent-gate/screening_findings — tool=get_incident_notes: 6 finding(s): email, export-all-data, ignore-instructions, phone, secret-exfil-url, ssn

**Evidenced (13):** AU-2 Event Logging · AU-3 Content of Audit Records (field check: 117/117 events carry the full core field set) · AU-9 Protection of Audit Information · AC-3 Access Enforcement · AC-6 Least Privilege · SI-4 System Monitoring · CM-3 Configuration Change Control · IR-4 Incident Handling (verify-failure → rollback → recorded `rolled_back`) · CP-4 Contingency Plan Testing · AI RMF GOVERN / MAP / MEASURE / MANAGE.

**Continuous checks (all pass on the drill store):** chain integrity · approval precedes execution (approval seq 11 < first executed step seq 14) · screening active · every decision record carries `computed=true` (4/4).

**Gaps (12, declared, not hidden):** AC-2 account management and IA-2 authentication (agents are name strings; the chain proves records weren't altered, not who wrote them) · AU-5 audit-failure response · AU-11 retention · SC-8 transport protection · SC-12 key management · SC-28 protection at rest (the store is plaintext; no redaction at capture) · CA-2 (this pack is not an assessment) · RA-3 formal risk assessment · AT-2/PS organizational controls · AI RMF GOVERN (organizational) and MAP (context & impact) documentary halves.

## How it works

```
atoinabox/
  storeio.py   load + verify an AgentTrace store (chain algorithm, fail-loud)
  controls.py  the catalog: mappings with evidence selectors + declared known gaps
  pack.py      mapping evaluation, continuous checks, pack JSON + assessor Markdown
  cli.py       python -m atoinabox build --store ... --out ...
```

Each catalog mapping declares *selector groups* over (producer, event-type) pairs. A control is `evidenced` only when every group matches at least one event; `partial` when some do; otherwise it joins the gaps. Citations are capped excerpts of the actual events — sequence, producer, type, timestamp, and a one-line summary pulled from the payload's deciding values (the BLOCK reasons, the screening patterns, the rollback detail), so an assessor reads what the artifact *says*, not just that it exists.

Control summaries in the catalog are short paraphrases; the "interpretation" attached to each mapping — how the control reads for an agent platform — is labeled as interpretation in the output. Authority rests with the source publications.

## Limitations

- **This is evidence organization, not a compliance certification.** It is not an assessor determination, not a system security plan, and not an Authorization to Operate. It assembles and cross-references machine-generated evidence; a human assessor still has to assess.
- **Standalone value is limited to platforms with similar telemetry.** The mappings are written against AgentTrace-schema events from this portfolio's producers. Another platform would need an ingestion adapter and a catalog review — the no-artifact-no-claim machinery carries over, the specific selectors don't.
- **Hash-chain verification proves tamper-evidence after the fact**, not producer identity (IA-2 gap) and not that a producer emitted *complete* records — a producer that never emits an event leaves no trace to verify. The gaps section says so rather than letting the green checkmarks imply otherwise.
- MAP is evidenced only in its failure-mode-catalog sense; the pack's own interpretation text states the limitation inline, next to the claim.

## Tests

```bash
python -m pytest
```

10 tests: every claim cites a real in-store event (seqs validated against the store), the gaps section is non-empty and contains every declared known gap, an unmatched mapping is demoted to gaps on a thin store, a tampered store is refused by default (exit 2, nothing written) and stamped when allowed (with AU-9 demoted), the continuous checks pass on the fixture, and an integration test runs the real 117-event drill store end to end.

## License

MIT
