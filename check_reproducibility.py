#!/usr/bin/env python3
"""Regenerate the dataset twice with the same seed and compare row counts + SHA-256 checksums.

    python check_reproducibility.py                 # full volume
    python check_reproducibility.py --scale 0.05    # quick check
Exit code 0 = identical, 1 = differences. Also writes reproducibility_report.json.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import credential_logic as L


def run(out, seed, scale, extra):
    cmd = [sys.executable, "generate_dataset.py", "--seed", str(seed), "--scale", str(scale), "--out", out] + extra
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return json.load(open(os.path.join(out, "source_manifest.json")))["files"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=L.DEFAULT_SEED)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--report", default="reproducibility_report.json")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        f1, f2 = run(d1, a.seed, a.scale, []), run(d2, a.seed, a.scale, [])
    rows, ok = [], True
    for fn in sorted(f1):
        same = f1[fn] == f2.get(fn)
        ok &= same
        rows.append({"file": fn, "rows_run1": f1[fn]["rows"], "rows_run2": f2[fn]["rows"],
                     "sha256_run1": f1[fn]["sha256"][:16], "sha256_run2": f2[fn]["sha256"][:16], "identical": same})
        print(f"{'OK ' if same else 'DIFF'} {fn:<38} rows {f1[fn]['rows']:>7} / {f2[fn]['rows']:>7}   {f1[fn]['sha256'][:16]} / {f2[fn]['sha256'][:16]}")
    json.dump({"seed": a.seed, "scale": a.scale, "all_identical": ok, "files": rows}, open(a.report, "w"), indent=2)
    print("\nREPRODUCIBLE: all files identical across two runs" if ok else "\nNOT REPRODUCIBLE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
