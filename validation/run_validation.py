#!/usr/bin/env python3
"""
run_validation.py — C3 orchestrator + metric ledger (the reusable backbone).

Runs every available validation layer over a corpus, aggregates pass/fail, prints
a single dashboard, and APPENDS a versioned metric vector to the ledger
(personas/_validation_ledger.jsonl) so drift across generator versions is visible.

Layers run (each is independent; a missing input degrades gracefully):
  L0  structural        -> generator/validate_personas.py
  L0  invariants        -> validation/test_invariants.py (anti-rot + property-based)
  L1  distributional    -> generator/distribution_report.py (+ census reference)
  L3  decision-model    -> validation/backtest_decision_model.py
  C2  fairness          -> validation/fairness_audit.py
  L2  C2ST              -> validation/c2st.py (only if --real <holdout> supplied)

Usage:
  python3 validation/run_validation.py personas/
  python3 validation/run_validation.py personas/ --reference reference/census_2011.json
  python3 validation/run_validation.py personas/ --real real_holdout.jsonl --fast
  python3 validation/run_validation.py personas/ --no-ledger

Exit code = number of failed gates (0 = all green).
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "generator")


def run(cmd, label):
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {"label": label, "cmd": " ".join(os.path.basename(c) if "/" in c else c for c in cmd),
            "exit": p.returncode, "passed": p.returncode == 0,
            "seconds": round(time.time() - t, 1),
            "stdout": p.stdout, "stderr": p.stderr[-2000:]}


def tail(s, n=4):
    lines = [l for l in s.strip().splitlines() if l.strip()]
    return lines[-n:]


def load_json(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference", "census_2011.json"))
    ap.add_argument("--real", help="real holdout .jsonl to enable L2 C2ST")
    ap.add_argument("--fast", action="store_true", help="smaller samples for speed")
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--invariant-n", type=int, default=5000)
    a = ap.parse_args()

    py = sys.executable
    results = []

    # L0 structural
    results.append(run([py, os.path.join(GEN, "validate_personas.py"), a.path,
                        "--fail-on-any", "--examples", "1"], "L0 structural"))
    # L0 invariants
    n = 2000 if a.fast else a.invariant_n
    results.append(run([py, os.path.join(HERE, "test_invariants.py"),
                        "--n", str(n)], "L0 invariants"))
    # L1 distributional
    dist_out = os.path.join(a.path, "_distribution_report.json")
    cmd = [py, os.path.join(GEN, "distribution_report.py"), a.path, "--out", dist_out]
    if os.path.exists(a.reference):
        cmd += ["--reference", a.reference]
    results.append(run(cmd, "L1 distributional"))
    # L3 decision model
    bt_out = os.path.join(a.path, "_backtest_report.json")
    samples = "120" if a.fast else "300"
    results.append(run([py, os.path.join(HERE, "backtest_decision_model.py"),
                        "--samples", samples, "--json", bt_out], "L3 decision-model"))
    # C2 fairness
    fair_out = os.path.join(a.path, "_fairness_report.json")
    results.append(run([py, os.path.join(HERE, "fairness_audit.py"), a.path,
                        "--out", fair_out], "C2 fairness"))
    # L2 C2ST (optional)
    if a.real:
        c2st_path = os.path.join(HERE, "c2st.py")
        if os.path.exists(c2st_path):
            results.append(run([py, c2st_path, a.path, "--real", a.real], "L2 C2ST"))

    # Dashboard
    print("\n" + "=" * 70)
    print(" PERSONA VALIDATION SUITE")
    print("=" * 70)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['label']:<22} ({r['seconds']}s)")
        for ln in tail(r["stdout"], 2):
            print(f"          {ln}")
        if not r["passed"] and r["stderr"].strip():
            print(f"          stderr: {r['stderr'].strip().splitlines()[-1]}")
    failed = [r for r in results if not r["passed"]]
    print("-" * 70)
    print(f" {len(results) - len(failed)}/{len(results)} gates green")
    print("=" * 70)

    # Metric ledger
    if not a.no_ledger:
        cov = load_json(os.path.join(a.path, "_coverage_report.json"))
        dist = load_json(dist_out)
        bt = load_json(bt_out)
        fair = load_json(fair_out)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total_personas": cov.get("total_personas") or dist.get("total_personas"),
            "generator": cov.get("generator"),
            "gates": {r["label"]: r["passed"] for r in results},
            "n_gates_failed": len(failed),
            "metrics": {
                "structural_anomalies": cov.get("validation_anomalies"),
                "dist_flags": len(dist.get("flags", [])),
                "dist_tv": {k: v.get("tv_vs_reference")
                            for k, v in dist.get("marginals", {}).items()
                            if v.get("tv_vs_reference") is not None},
                "backtest_brier_primary": bt.get("brier_primary"),
                "backtest_pass": bt.get("n_pass"),
                "backtest_directional": bt.get("directional_pass"),
                "fairness_ci_flags": len(fair.get("conditional_independence", [])),
            },
        }
        ledger = os.path.join(a.path, "_validation_ledger.jsonl")
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f" ledger += {ledger}")
        # drift note vs previous entry
        prev = [json.loads(l) for l in open(ledger, encoding="utf-8") if l.strip()]
        if len(prev) >= 2:
            a0, a1 = prev[-2]["metrics"], prev[-1]["metrics"]
            drift = []
            for k in ("backtest_brier_primary", "dist_flags", "structural_anomalies",
                      "fairness_ci_flags"):
                if a0.get(k) != a1.get(k):
                    drift.append(f"{k}: {a0.get(k)} -> {a1.get(k)}")
            if drift:
                print(" drift vs previous run: " + "; ".join(drift))

    sys.exit(len(failed))


if __name__ == "__main__":
    main()
