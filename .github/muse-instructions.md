# Copilot instructions — ato-in-a-box

You are working in **ATO-in-a-Box**: it turns an AgentTrace store into
an assessor-ready compliance evidence pack — platform controls mapped
to NIST SP 800-53 Rev. 5 controls and NIST AI RMF functions, every
mapping citing the concrete artifact that evidences it, plus an
explicit gaps section for what the evidence does not cover.

## Stack

- Python 3; package `atoinabox/`: `storeio.py` (store loading + chain
  re-verification), `controls.py` (the mapping catalog and declared
  gaps), `pack.py` (evaluation + assessor-document rendering),
  `cli.py`.
- CLI: `python -m atoinabox build --store <store.jsonl> --out <dir>`
  producing `evidence-pack.json` + `evidence-pack.md`.

## Tests

```bash
python -m pytest   # 10 tests, including an integration test on the real drill store
```

## Architecture notes

- The rule the tool is built around: no artifact, no claim. A control
  is `evidenced` only when every evidence selector group matches at
  least one real event; otherwise the mapping is demoted to the gaps
  section automatically — by construction, not by reviewer discipline.
- `storeio.py` re-implements chain verification on purpose: the
  consumer never trusts the producer's verifier. A broken chain makes
  the CLI refuse (exit 2, nothing written); `--allow-broken` stamps
  the pack INTEGRITY: BROKEN everywhere and demotes chain-dependent
  controls (e.g. AU-9) to gaps.
- Citations are real events — seq, producer, type, timestamp, and a
  payload-derived summary. Never write a citation you didn't read
  from the store.
- This is evidence organization, not a compliance certification, and
  the gaps section is a feature: keep it explicit and honest in every
  output.

## Shared rules

- Use Unix LF line endings in every file; never CRLF.
- Never commit secrets, tokens, or credentials — real or synthetic-looking.
- Tests must pass before you describe a change as complete; run the test
  command above and report honestly if you cannot.
- Prefer the smallest complete implementation: reuse what already exists in
  this repo before adding new code, files, or dependencies.
