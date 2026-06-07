#!/usr/bin/env python3
"""
fairness_audit.py — C2 fairness / stereotype audit.

Two checks, stdlib-only:

  1. CONDITIONAL-INDEPENDENCE (generator-bias). The generator must not couple a
     sensitive attribute (religion, community/caste) to life outcomes BEYOND what
     it already encodes through legitimate demographics. So: control on class_nccs
     (which legitimately drives income & loss-aversion), then test whether outcome
     distributions (loss-aversion, income_band, education, dominant_traits) are
     ~independent of the sensitive attribute WITHIN each control stratum. A large
     within-stratum Total-Variation divergence between a group and the pooled
     distribution = the generator is inventing prejudicial coupling. (Real-world
     caste/income correlation is allowed *through* nccs; what we forbid is extra
     coupling the generator adds on top.)

  2. STEREOTYPE LEXICON SCAN. Flags demeaning descriptor terms appearing in a
     persona's free text, and any sensitive group that co-occurs with negative
     descriptors at a disproportionate rate vs the pooled base rate.

Usage:
  python3 validation/fairness_audit.py personas/
  python3 validation/fairness_audit.py personas/ --tv-threshold 0.08 --out report.json
"""
import argparse, glob, json, os, sys
from collections import defaultdict, Counter

SENSITIVE = ["religion", "community"]
CONTROL = "class_nccs"
# Outcome extractors: name -> (callable(persona) -> bucket value or None)
def lam_bucket(p):
    lam = p.get("decision_model", {}).get("prospect", {}).get("loss_aversion_lambda")
    if not isinstance(lam, (int, float)):
        return None
    return f"{round(lam*2)/2:.1f}"  # 0.5-wide buckets

OUTCOMES = {
    "loss_aversion": lam_bucket,
    "income_band": lambda p: p.get("identity", {}).get("income_band"),
    "education": lambda p: p.get("identity", {}).get("education"),
    "occupation_tier": lambda p: p.get("identity", {}).get("occupation_tier"),
}

# Demeaning descriptor terms that must never be tied to a group in free text.
DEMEANING = ["lazy", "dirty", "criminal", "backward", "savage", "untouchable",
             "inferior", "stupid", "uncivilized", "thief", "dishonest", "filthy",
             "subhuman", "primitive"]


def tv(emp, pooled):
    se, sp = sum(emp.values()) or 1, sum(pooled.values()) or 1
    keys = set(emp) | set(pooled)
    return 0.5 * sum(abs(emp.get(k, 0) / se - pooled.get(k, 0) / sp) for k in keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--tv-threshold", type=float, default=0.08)
    ap.add_argument("--min-stratum", type=int, default=2000,
                    help="skip control strata smaller than this")
    ap.add_argument("--min-group", type=int, default=400,
                    help="skip a group within a stratum below this n (noise floor)")
    ap.add_argument("--out", default="fairness_report.json")
    a = ap.parse_args()
    files = sorted(f for f in glob.glob(os.path.join(a.path, "*.jsonl")) if not os.path.basename(f).startswith("_")) if os.path.isdir(a.path) else [a.path]
    if not files:
        sys.exit("no .jsonl found")

    # counts[sensitive][outcome][control_stratum][group][value] = n
    counts = {s: {o: defaultdict(lambda: defaultdict(Counter)) for o in OUTCOMES} for s in SENSITIVE}
    # stereotype: per-group demeaning hits + group totals
    group_total = {s: Counter() for s in SENSITIVE}
    group_demean = {s: Counter() for s in SENSITIVE}
    demean_examples = []
    total = 0

    for fn in files:
        for line in open(fn, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            total += 1
            idn = p.get("identity", {})
            ctrl = idn.get(CONTROL)
            blob = json.dumps({k: p.get(k) for k in
                               ("dominant_traits", "quirks", "core_values", "portrait",
                                "psychological_paradoxes", "stress_and_coping")}).lower()
            hits = [w for w in DEMEANING if w in blob]
            for s in SENSITIVE:
                g = idn.get(s)
                if g is None:
                    continue
                group_total[s][g] += 1
                if hits:
                    group_demean[s][g] += 1
                    if len(demean_examples) < 15:
                        demean_examples.append({"name": p.get("name"), s: g, "terms": hits})
                if ctrl is None:
                    continue
                for o, fn_o in OUTCOMES.items():
                    v = fn_o(p)
                    if v is not None:
                        counts[s][o][ctrl][g][v] += 1

    report = {"total": total, "conditional_independence": [], "stereotype": {}}
    # conditional-independence flags
    for s in SENSITIVE:
        for o in OUTCOMES:
            for ctrl, by_group in counts[s][o].items():
                pooled = Counter()
                for g, c in by_group.items():
                    pooled.update(c)
                if sum(pooled.values()) < a.min_stratum:
                    continue
                for g, c in by_group.items():
                    if sum(c.values()) < a.min_group:
                        continue
                    d = tv(c, pooled)
                    if d > a.tv_threshold:
                        report["conditional_independence"].append({
                            "sensitive": s, "outcome": o, "control": f"{CONTROL}={ctrl}",
                            "group": g, "tv_vs_pooled": round(d, 4),
                            "n_group": sum(c.values())})
    # stereotype rates
    for s in SENSITIVE:
        base = sum(group_demean[s].values()) / max(1, sum(group_total[s].values()))
        rows = []
        for g, tot in group_total[s].most_common():
            rate = group_demean[s][g] / tot if tot else 0
            rows.append({"group": g, "n": tot, "demeaning_rate": round(rate, 5),
                         "vs_base": round(rate - base, 5)})
        report["stereotype"][s] = {"base_rate": round(base, 5), "groups": rows}
    report["stereotype"]["examples"] = demean_examples

    json.dump(report, open(a.out, "w"), indent=2)

    print(f"\nC2 fairness audit — {total:,} personas")
    print("=" * 64)
    ci = report["conditional_independence"]
    print(f"1. Conditional-independence (control={CONTROL}, TV>{a.tv_threshold}):")
    if not ci:
        print("   PASS — no outcome diverges by religion/community within strata")
    else:
        print(f"   {len(ci)} FLAG(S):")
        for f in ci[:20]:
            print(f"   ! {f['sensitive']}={f['group']} | {f['outcome']} | "
                  f"{f['control']}  TV={f['tv_vs_pooled']} (n={f['n_group']})")
    print("2. Stereotype lexicon scan:")
    tot_demean = sum(sum(group_demean[s].values()) for s in SENSITIVE)
    if tot_demean == 0:
        print("   PASS — zero demeaning descriptors in any persona free text")
    else:
        print(f"   {tot_demean} demeaning-term hits; see report for group rates")
        for s in SENSITIVE:
            for r in report["stereotype"][s]["groups"]:
                if r["demeaning_rate"] > 0:
                    print(f"   ! {s}={r['group']} rate={r['demeaning_rate']} "
                          f"(base {report['stereotype'][s]['base_rate']})")
    print("=" * 64)
    print(f"-> {a.out}")
    ok = not ci and tot_demean == 0
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
