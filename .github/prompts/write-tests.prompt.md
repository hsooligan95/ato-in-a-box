---
mode: agent
description: Write tests for a named module in ato-in-a-box
---

Write tests for the module I name, following this repo's existing test
style, layout, and fixtures. Cover the behavior the module documents,
including these invariants where they apply:

- No artifact, no claim: a control is evidenced only when every evidence selector group matches at least one real event, otherwise it is demoted to gaps automatically.
- storeio.py re-verifies the hash chain independently; a broken chain makes the CLI refuse (exit 2, nothing written) unless --allow-broken stamps the pack BROKEN.
- Citations are real events (seq, producer, type, timestamp, payload-derived summary) — never write a citation you didn't read from the store.

Then run the test suite:

    python -m pytest

Show the result. Do not claim done unless the suite is green; if a
test cannot pass, say why instead of weakening the assertion.
