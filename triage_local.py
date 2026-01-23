#!/usr/bin/env python3
# triage_local.py
#
# Read fetched email JSON files (from fetch_full.py output),
# classify + prioritize, and emit draft triage JSON for each email.
#
# Expected input files (default):
#   out/emails/*.json
#
# Output (default):
#   out/triage/<email_id>.triage.json

from __future__ import annotations

import argparse
import os

from triage_core import (
    discover_input_files,
    dump_json,
    ensure_dir,
    load_json,
    triage_one,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-glob", default="out/emails/*.json", help="e.g. out/emails/*.json")
    ap.add_argument("--output-dir", default="out/triage", help="e.g. out/triage")
    ap.add_argument("--max-results", type=int, default=50, help="limit processed emails")
    args = ap.parse_args()

    files = discover_input_files(args.input_glob)
    if not files:
        print(f"No input files matched: {args.input_glob}")
        return

    out_dir = args.output_dir
    ensure_dir(out_dir)

    processed = 0
    for path in files:
        if processed >= args.max_results:
            break

        try:
            email = load_json(path)
        except Exception as e:
            print(f"Skip (bad json): {path} -> {e}")
            continue

        triaged = triage_one(email)
        email_id = triaged.get("email_id") or os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(out_dir, f"{email_id}.triage.json")

        dump_json(out_path, triaged)
        processed += 1
        print(f"triaged: {email_id} -> {out_path}")

    print(f"Done. triaged={processed}, output_dir={out_dir}")


if __name__ == "__main__":
    main()
