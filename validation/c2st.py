#!/usr/bin/env python3
"""
c2st.py — L2 Classifier Two-Sample Test (stdlib-only logistic regression).

Trains a classifier to distinguish REAL records from SYNTHETIC personas on their
demographic features. Interpretation:

  AUC ~ 0.50  -> indistinguishable (synthetic matches real)  [GOOD]
  AUC -> 1.00 -> trivially separable; the top-weighted features are exactly the
                 fields that give the synthetic data away      [BLEED-BUG RADAR]

Also reports the highest-magnitude coefficients so you know WHICH field to fix.

Requires a real holdout in the same JSON shape (at least the identity/background
fields). Without --real, runs a SELF-TEST: splits the synthetic corpus in two and
confirms AUC ~ 0.5 (sanity check that the harness itself is unbiased).

Usage:
  python3 validation/c2st.py personas/ --real real_holdout.jsonl
  python3 validation/c2st.py personas/                      # self-test
  python3 validation/c2st.py personas/ --real r.jsonl --max 20000 --auc-threshold 0.6
"""
import argparse, glob, json, math, os, random, sys

# Categorical features one-hot encoded; age is numeric (standardised).
CAT_FEATURES = [
    ("identity", "gender"), ("identity", "state"), ("identity", "region"),
    ("identity", "setting"), ("identity", "religion"), ("identity", "community"),
    ("identity", "occupation_tier"), ("identity", "education"),
    ("identity", "class_nccs"), ("identity", "income_band"),
    ("background", "marital_status"), ("background", "household"),
]


def get(p, path):
    cur = p
    for k in path:
        cur = (cur or {}).get(k) if isinstance(cur, dict) else None
    return cur


def read(path, limit):
    files = sorted(f for f in glob.glob(os.path.join(path, "*.jsonl")) if not os.path.basename(f).startswith("_")) if os.path.isdir(path) else [path]
    rows = []
    for fn in files:
        for line in open(fn, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                return rows
    return rows


def build_vocab(rows):
    vocab = {}  # (field, value) -> index
    for p in rows:
        for f in CAT_FEATURES:
            key = (".".join(f), str(get(p, f)))
            if key not in vocab:
                vocab[key] = len(vocab)
    vocab[("__age__", "")] = len(vocab)
    vocab[("__bias__", "")] = len(vocab)
    return vocab


def featurize(p, vocab, age_mean, age_std):
    x = {}
    for f in CAT_FEATURES:
        key = (".".join(f), str(get(p, f)))
        if key in vocab:
            x[vocab[key]] = 1.0
    age = get(p, ("identity", "age"))
    if isinstance(age, (int, float)):
        x[vocab[("__age__", "")]] = (age - age_mean) / (age_std or 1)
    x[vocab[("__bias__", "")]] = 1.0
    return x


def sigmoid(z):
    if z < -700:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def train_logreg(X, y, dim, epochs=40, lr=0.3, l2=1e-4):
    w = [0.0] * dim
    idx = list(range(len(X)))
    for _ in range(epochs):
        random.shuffle(idx)
        for i in idx:
            xi, yi = X[i], y[i]
            z = sum(w[j] * v for j, v in xi.items())
            err = sigmoid(z) - yi
            for j, v in xi.items():
                w[j] -= lr * (err * v + l2 * w[j])
    return w


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return 0.5
    # rank-based (Mann-Whitney U)
    paired = sorted(zip(scores, labels), key=lambda t: t[0])
    rank = {}
    i = 0
    while i < len(paired):
        j = i
        while j < len(paired) and paired[j][0] == paired[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            rank[k] = avg
        i = j
    sum_pos = sum(rank[k] for k, (_, l) in enumerate(paired) if l == 1)
    n_pos, n_neg = len(pos), len(neg)
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--real", help="real holdout .jsonl")
    ap.add_argument("--max", type=int, default=15000, help="max rows per class")
    ap.add_argument("--auc-threshold", type=float, default=0.60)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="c2st_report.json")
    a = ap.parse_args()
    random.seed(a.seed)

    syn = read(a.path, a.max * 2)
    random.shuffle(syn)
    self_test = not a.real
    if self_test:
        half = min(a.max, len(syn) // 2)
        real_rows, syn_rows = syn[:half], syn[half:half * 2]
    else:
        real_rows = read(a.real, a.max)
        syn_rows = syn[:max(len(real_rows), a.max)][:len(real_rows) * 3 if real_rows else a.max]

    rows = [(r, 1) for r in real_rows] + [(s, 0) for s in syn_rows]
    random.shuffle(rows)
    ages = [get(p, ("identity", "age")) for p, _ in rows if isinstance(get(p, ("identity", "age")), (int, float))]
    age_mean = sum(ages) / len(ages) if ages else 30
    age_std = (sum((x - age_mean) ** 2 for x in ages) / len(ages)) ** 0.5 if ages else 1

    vocab = build_vocab([p for p, _ in rows])
    dim = len(vocab)
    X = [featurize(p, vocab, age_mean, age_std) for p, _ in rows]
    y = [lab for _, lab in rows]
    cut = int(len(X) * 0.7)
    w = train_logreg(X[:cut], y[:cut], dim)
    scores = [sum(w[j] * v for j, v in xi.items()) for xi in X[cut:]]
    a_uc = auc(scores, y[cut:])

    inv = {i: k for k, i in vocab.items()}
    top = sorted(range(dim), key=lambda j: -abs(w[j]))
    top_feats = [{"feature": f"{inv[j][0]}={inv[j][1]}", "weight": round(w[j], 3)}
                 for j in top[:15] if inv[j][0] not in ("__bias__",)]

    report = {"mode": "self_test" if self_test else "real_vs_synthetic",
              "n_real": len(real_rows), "n_synthetic": len(syn_rows),
              "auc": round(a_uc, 4), "auc_threshold": a.auc_threshold,
              "top_discriminating_features": top_feats}
    json.dump(report, open(a.out, "w"), indent=2)

    print(f"\nL2 Classifier Two-Sample Test ({report['mode']})")
    print("=" * 60)
    print(f"  real={len(real_rows)}  synthetic={len(syn_rows)}")
    print(f"  AUC = {a_uc:.4f}   (0.5 = indistinguishable, 1.0 = separable)")
    if self_test:
        ok = abs(a_uc - 0.5) < 0.05
        print(f"  SELF-TEST: harness {'UNBIASED (PASS)' if ok else 'BIASED (FAIL)'} "
              f"— expected AUC~0.5")
    else:
        ok = a_uc <= a.auc_threshold
        print(f"  {'PASS' if ok else 'FAIL'} (threshold {a.auc_threshold})")
        if not ok:
            print("  Top fields giving synthetic away (fix these):")
            for tf in top_feats[:8]:
                print(f"    {tf['weight']:+.2f}  {tf['feature']}")
    print("=" * 60)
    print(f"-> {a.out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
