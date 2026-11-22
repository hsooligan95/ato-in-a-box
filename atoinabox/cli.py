"""ATO-in-a-Box CLI.

    python -m atoinabox build --store <agenttrace store.jsonl> --out <dir>

Exit codes: 0 = pack generated from a verified chain;
2 = chain broken and pack refused (nothing written);
3 = store unreadable. With --allow-broken, a broken chain still
generates, stamped BROKEN in the JSON, the Markdown, and this output.
"""

from __future__ import annotations

import argparse
import sys

from .pack import build_pack, find_tamper_demonstration, write_pack
from .storeio import StoreError


def cmd_build(args) -> int:
    try:
        tamper = find_tamper_demonstration(args.store)
        pack, chain = build_pack(args.store, tamper_note=tamper)
    except StoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    if not chain.ok and not args.allow_broken:
        print(f"REFUSED: hash chain broken at seq {chain.broken_seq} ({chain.detail}). "
              "No pack written. Re-run with --allow-broken to generate a stamped pack.",
              file=sys.stderr)
        return 2
    json_path, md_path = write_pack(pack, args.out)
    s = pack["summary"]
    stamp = "" if chain.ok else " [STAMPED: INTEGRITY BROKEN]"
    print(f"pack written: {json_path} + {md_path}{stamp}")
    print(f"integrity: {pack['integrity']['status']} ({chain.count} events) · "
          f"evidenced: {s['evidenced']} · partial: {s['partial']} · gaps: {s['gaps']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atoinabox", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="build an evidence pack from an AgentTrace store")
    p.add_argument("--store", required=True, help="path to the AgentTrace store.jsonl")
    p.add_argument("--out", required=True, help="output directory for the pack")
    p.add_argument("--allow-broken", action="store_true",
                   help="generate a stamped pack even if the hash chain is broken")
    p.set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
