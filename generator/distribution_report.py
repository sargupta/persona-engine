#!/usr/bin/env python3
"""
distribution_report.py — L1 distributional-fidelity profiler.

Computes the corpus's marginal and joint distributions for the demographic
fields, plus per-field entropy, mode-collapse flags, and coverage holes. If a
reference distribution file is supplied (real ground truth — Census 2011 /
NFHS-5 / PLFS / NCCS), it also reports the Total-Variation distance per marginal
so you can gate on demographic realism.

This is the first rung of the validation pyramid above the (circular) structural
validator — see research/persona-validation-and-verification-framework.md.

Usage:
  python3 distribution_report.py personas/                         # profile only
  python3 distribution_report.py personas/ --reference ref.json    # + TV vs truth
  python3 distribution_report.py personas/ --out dist_report.json

Reference file schema (all keys optional; supply what you have):
  { "marginals": { "<field>": { "<value>": <probability 0..1>, ... }, ... } }
e.g.  { "marginals": { "religion": { "Hindu": 0.798, "Muslim": 0.142, ... } } }
Probabilities per field should sum to ~1; they are renormalised defensively.
"""
import argparse, glob, json, math, os, sys
from collections import Counter, defaultdict

# Marginal fields to profile (single-value categorical/ordinal).
MARGINAL_FIELDS = [
    ("identity", "gender"), ("identity", "state"), ("identity", "region"),
    ("identity", "setting"), ("identity", "religion"), ("identity", "community"),
    ("identity", "occupation_tier"), ("identity", "education"),
    ("identity", "class_nccs"), ("identity", "income_band"),
    ("background", "marital_status"), ("background", "household"),
]
# Joints where contamination/implausibility actually shows up.
JOINT_FIELDS = [
    (("identity", "occupation_tier"), ("identity", "education")),
    (("background", "marital_status"), ("background", "children_band")),
    (("identity", "state"), ("identity", "religion")),
    (("identity", "gender"), ("identity", "occupation_tier")),
]
AGE_BANDS = [(0, 17, "<18"), (18, 25, "18-25"), (26, 35, "26-35"),
             (36, 45, "36-45"), (46, 60, "46-60"), (61, 200, "60+")]


def age_band(a):
    for lo, hi, label in AGE_BANDS:
        if lo <= a <= hi:
            return label
    return "?"


def children_band(c):
    if c is None:
        return "?"
    return "0" if c == 0 else "1" if c == 1 else "2" if c == 2 else "3+"


def get(p, path):
    cur = p
    for k in path:
        cur = (cur or {}).get(k) if isinstance(cur, dict) else None
    return cur


def entropy(counter):
    n = sum(counter.values())
    if n == 0:
        return 0.0
    h = -sum((v / n) * math.log2(v / n) for v in counter.values() if v)
    return h


def normalised_entropy(counter):
    k = len([v for v in counter.values() if v])
    if k <= 1:
        return 0.0
    return entropy(counter) / math.log2(k)


def tv_distance(emp, ref):
    """Total-variation distance between two prob dicts (renormalised)."""
    se, sr = sum(emp.values()) or 1, sum(ref.values()) or 1
    keys = set(emp) | set(ref)
    return 0.5 * sum(abs(emp.get(k, 0) / se - ref.get(k, 0) / sr) for k in keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--reference", help="JSON of real ground-truth distributions")
    ap.add_argument("--out", default="distribution_report.json")
    ap.add_argument("--tv-threshold", type=float, default=0.10)
    ap.add_argument("--collapse-threshold", type=float, default=0.60,
                    help="flag a field whose single top value exceeds this share")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.path, "*.jsonl"))) if os.path.isdir(a.path) else [a.path]
    if not files:
        sys.exit("no .jsonl files found at " + a.path)

    marg = {f: Counter() for f in MARGINAL_FIELDS}
    marg_age = Counter()
    joints = {j: Counter() for j in JOINT_FIELDS}
    total = 0
    for fn in files:
        for line in open(fn, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            total += 1
            for f in MARGINAL_FIELDS:
                v = get(p, f)
                if v is not None:
                    marg[f][v] += 1
            age = get(p, ("identity", "age"))
            if isinstance(age, int):
                marg_age[age_band(age)] += 1
            for (fa, fb) in JOINT_FIELDS:
                va = children_band(get(p, ("background", "children"))) if fb[-1] == "children_band" and fb[0] == "background" else None
                a_val = get(p, fa)
                b_val = children_band(get(p, ("background", "children"))) if fb == ("background", "children_band") else get(p, fb)
                if a_val is not None and b_val is not None:
                    joints[(fa, fb)][(a_val, b_val)] += 1

    report = {"total_personas": total, "marginals": {}, "joints": {}, "flags": []}

    # Age marginal (derived)
    report["marginals"]["identity.age_band"] = {
        "distribution": {k: round(v / total, 5) for k, v in marg_age.most_common()},
        "entropy_normalised": round(normalised_entropy(marg_age), 4),
    }

    ref = json.load(open(a.reference)) if a.reference else {}
    ref_marg = ref.get("marginals", {})

    for f, ctr in marg.items():
        key = ".".join(f)
        dist = {k: round(v / total, 5) for k, v in ctr.most_common()}
        ne = normalised_entropy(ctr)
        entry = {"distribution": dist, "entropy_normalised": round(ne, 4),
                 "distinct": len(ctr)}
        top_val, top_n = ctr.most_common(1)[0] if ctr else (None, 0)
        top_share = top_n / total if total else 0
        if top_share > a.collapse_threshold:
            report["flags"].append(
                f"MODE_COLLAPSE {key}: '{top_val}' = {top_share:.1%} of corpus")
        if ne < 0.5 and len(ctr) > 2:
            report["flags"].append(
                f"LOW_ENTROPY {key}: normalised entropy {ne:.2f} (<0.5)")
        # TV vs reference if provided
        rk = ref_marg.get(key) or ref_marg.get(f[-1])
        if rk:
            emp = {k: v / total for k, v in ctr.items()}
            tv = tv_distance(emp, rk)
            entry["tv_vs_reference"] = round(tv, 4)
            status = "OK" if tv <= a.tv_threshold else "FAIL"
            entry["tv_status"] = status
            if status == "FAIL":
                report["flags"].append(
                    f"DIST_DRIFT {key}: TV {tv:.3f} > {a.tv_threshold} vs reference")
            # coverage holes: real values absent from corpus
            missing = [k for k in rk if k not in ctr]
            if missing:
                report["flags"].append(
                    f"COVERAGE_HOLE {key}: real values absent from corpus: {missing}")
        report["marginals"][key] = entry

    for (fa, fb), ctr in joints.items():
        key = ".".join(fa) + " x " + (fb[-1] if fb[0] == "background" else ".".join(fb))
        top = ctr.most_common(12)
        report["joints"][key] = {
            "distinct_cells": len(ctr),
            "top_cells": [{"cell": list(c), "share": round(n / total, 5)} for c, n in top],
            "entropy_normalised": round(normalised_entropy(ctr), 4),
        }

    json.dump(report, open(a.out, "w"), indent=2, default=str)

    # Console summary
    print(f"\nProfiled {total:,} personas across {len(files)} file(s)")
    print("-" * 64)
    for key, e in report["marginals"].items():
        tv = e.get("tv_vs_reference")
        tvs = f"  TV={tv} [{e.get('tv_status')}]" if tv is not None else ""
        print(f"  {key:<28} distinct={e.get('distinct','-'):>3}  "
              f"H={e['entropy_normalised']:.2f}{tvs}")
    print("-" * 64)
    if report["flags"]:
        print(f"{len(report['flags'])} FLAG(S):")
        for fl in report["flags"]:
            print("  ! " + fl)
    else:
        print("No distributional flags (no reference = profile-only run).")
    print(f"\nFull report -> {a.out}")
    if a.reference and any(f.startswith("DIST_DRIFT") or f.startswith("COVERAGE_HOLE")
                           for f in report["flags"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
