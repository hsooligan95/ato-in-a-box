import json
from pathlib import Path

import pytest
from conftest import fixture_events, write_store

from atoinabox.cli import main as cli_main
from atoinabox.controls import KNOWN_GAPS
from atoinabox.pack import build_pack, render_markdown
from atoinabox.storeio import verify

DRILL_STORE = (Path(__file__).resolve().parent.parent.parent
               / "agent-trace" / "drill" / "output" / "trace-drill-45d404d0" / "store.jsonl")


@pytest.fixture()
def store(tmp_path):
    return write_store(tmp_path / "store.jsonl", fixture_events())


def test_fixture_chain_verifies(store):
    assert verify(store).ok


def test_every_claim_cites_a_real_event(store):
    """No artifact, no claim: every evidenced/partial control cites only
    seqs that exist in the store, and every matched group has citations."""
    pack, chain = build_pack(store)
    assert chain.ok
    valid_seqs = set(range(1, chain.count + 1))
    assert pack["controls"], "fixture store should evidence some controls"
    for control in pack["controls"]:
        assert control["status"] in ("evidenced", "partial")
        for group in control["evidence_groups"]:
            if group["match_count"] > 0:
                assert group["citations"], f"{control['id']}: matched group without citations"
                for cit in group["citations"]:
                    assert cit["seq"] in valid_seqs
                    assert cit["summary"]
            else:
                assert group["citations"] == []


def test_all_catalog_mappings_evidenced_on_fixture(store):
    pack, _ = build_pack(store)
    by_id = {c["id"]: c["status"] for c in pack["controls"]}
    for expected in ("AU-2", "AU-3", "AU-9", "AC-3", "AC-6", "SI-4", "CM-3",
                     "IR-4", "CP-4", "GOVERN", "MAP", "MEASURE", "MANAGE"):
        assert by_id.get(expected) == "evidenced", f"{expected}: {by_id.get(expected)}"


def test_gaps_section_nonempty_and_honest(store):
    pack, _ = build_pack(store)
    assert pack["gaps"], "gaps section must never be empty"
    gap_ids = {g["id"] for g in pack["gaps"]}
    for declared in KNOWN_GAPS:
        assert declared["id"] in gap_ids
    for gap in pack["gaps"]:
        assert gap["gap"] and gap["remediation"]


def test_unmatched_mapping_is_demoted_to_gaps(tmp_path):
    """A store with almost nothing in it must claim almost nothing."""
    from conftest import ev, write_store as ws
    store = ws(tmp_path / "thin.jsonl", [ev("agent-ledger", "span", {"name": "x"})])
    pack, _ = build_pack(store)
    claimed = {c["id"] for c in pack["controls"]}
    gap_ids = {g["id"] for g in pack["gaps"]}
    assert "AC-3" not in claimed and "AC-3" in gap_ids
    assert "AU-9" in claimed  # chain itself is intact, events exist
    assert pack["summary"]["gaps"] > len(KNOWN_GAPS)


def test_broken_chain_refused_by_default(store, tmp_path):
    lines = store.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[3])
    tampered["payload"] = {"forged": True}
    lines[3] = json.dumps(tampered)
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = cli_main(["build", "--store", str(bad), "--out", str(out)])
    assert rc == 2
    assert not (out / "evidence-pack.json").exists()


def test_broken_chain_stamped_when_allowed(store, tmp_path):
    lines = store.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[3])
    tampered["payload"] = {"forged": True}
    lines[3] = json.dumps(tampered)
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = cli_main(["build", "--store", str(bad), "--out", str(out), "--allow-broken"])
    assert rc == 0
    pack = json.loads((out / "evidence-pack.json").read_text(encoding="utf-8"))
    assert pack["integrity"]["status"] == "BROKEN"
    assert pack["integrity"]["broken_seq"] == 4
    md = (out / "evidence-pack.md").read_text(encoding="utf-8")
    assert "INTEGRITY: BROKEN" in md
    # AU-9 leans on the chain: with the chain broken it must not be claimed.
    claimed = {c["id"] for c in pack["controls"]}
    assert "AU-9" not in claimed


def test_checks_pass_on_fixture(store):
    pack, _ = build_pack(store)
    results = {c["id"]: c["result"] for c in pack["checks"]}
    assert results["chain-integrity"] == "pass"
    assert results["approval-precedes-execution"] == "pass"
    assert results["screening-active"] == "pass"
    assert results["decision-records-computed"] == "pass"


def test_markdown_renders_matrix_and_gaps(store):
    pack, _ = build_pack(store)
    md = render_markdown(pack)
    assert "## 2. Control evidence matrix" in md
    assert "## 3. Gaps" in md
    assert "seq 2" in md  # a concrete citation made it into the document
    assert "not a" in md and "certification" in md  # disclaimer present


@pytest.mark.skipif(not DRILL_STORE.exists(), reason="agent-trace drill store not present")
def test_real_drill_store():
    """Integration: the phase-2 proof drill store (117 events, 6 producers)."""
    pack, chain = build_pack(DRILL_STORE)
    assert chain.ok and chain.count == 117
    assert pack["source_store"]["producers"] == sorted(
        ["agent-canary", "agent-chaos", "agent-gate", "agent-ledger",
         "blast-radius", "factory-floor-agent"])
    by_id = {c["id"]: c for c in pack["controls"]}
    for expected in ("AU-2", "AU-3", "AU-9", "AC-3", "AC-6", "SI-4", "CM-3",
                     "IR-4", "CP-4", "GOVERN", "MEASURE", "MANAGE"):
        assert by_id[expected]["status"] == "evidenced", expected
    # The canary BLOCK and the gate screening must appear as citations.
    cm3 = json.dumps(by_id["CM-3"])
    assert "BLOCK" in cm3
    si4 = json.dumps(by_id["SI-4"])
    assert "ignore-instructions" in si4
    assert pack["summary"]["gaps"] >= len(KNOWN_GAPS)
