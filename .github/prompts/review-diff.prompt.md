---
mode: agent
description: Review the current diff against ato-in-a-box's invariants
---

Review my current diff against this repo's invariants:

- No artifact, no claim: a control is evidenced only when every evidence selector group matches at least one real event, otherwise it is demoted to gaps automatically.
- storeio.py re-verifies the hash chain independently; a broken chain makes the CLI refuse (exit 2, nothing written) unless --allow-broken stamps the pack BROKEN.
- Citations are real events (seq, producer, type, timestamp, payload-derived summary) — never write a citation you didn't read from the store.
- The gaps section stays explicit and honest: this is evidence organization, not a compliance certification.

Flag every violation with file and line. Also flag any change that
alters a documented behavior contract (output shapes, exit codes,
event schemas, recorded artifacts) without updating the docs and
tests that describe it. No style nitpicks — correctness and contract
violations only.
