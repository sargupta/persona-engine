#!/usr/bin/env python3
"""
test_invariants.py — L0 hardening (stdlib property-based + anti-rot).

Two guarantees, no third-party deps:

  A. ANTI-ROT — replays fixtures/negative_corpus.jsonl (one known-bad persona per
     validator rule) and asserts the structural validator still flags each one.
     A validator that silently stops catching a class fails here.

  B. PROPERTY-BASED — generates N fresh personas from the factory across randomised
     seeds and asserts hard invariants that must hold for EVERY persona:
       - structural validator returns zero flags
       - tier ⇒ allowed-education (no graduate masons)
       - children==0 ⇒ no child reference anywhere in free text
       - gender=='M' ⇒ no she/her in free text
       - required schema fields all present
       - decision_model present and internally sane (probabilities in range)

Exit code 0 = all green; 1 = any failure (CI-gateable).

Usage:
  python3 validation/test_invariants.py            # default 5000 personas
  python3 validation/test_invariants.py --n 20000
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(HERE), "generator")
sys.path.insert(0, GEN)
import persona_factory as pf      # noqa: E402
import validate_personas as vp    # noqa: E402

CHILD = re.compile(r"child's|children's|childcare|the kids|for the kids|kids'")
SHE = re.compile(r"\bher\b|\bshe\b")
TIER_EDU = {  # tier -> education values that must NEVER appear for that tier
    "manual": {"a graduate degree", "a postgraduate degree"},
}
CHILD_SCOPE = ("motivations", "daily_rhythm", "psychological_paradoxes",
               "cognitive_architecture", "contextual_dynamics")
GENDER_SCOPE = ("background", "psychological_paradoxes", "cognitive_architecture",
                "contextual_dynamics", "stress_and_coping", "motivations")


def fails(cond, msg, bucket):
    if cond:
        bucket.append(msg)


def test_negative_corpus():
    path = os.path.join(HERE, "fixtures", "negative_corpus.jsonl")
    errs = []
    n = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        n += 1
        p = json.loads(line)
        expect = p.pop("_expect")
        flags = vp.check(p)
        fails(expect not in flags,
              f"negative fixture for '{expect}' NOT flagged (got {flags})", errs)
    return n, errs


def test_property_based(n_personas, seed0):
    errs = []
    for i in range(n_personas):
        pf.random.seed(seed0 + i)
        p = pf.build_persona()
        name = p.get("name", "?")
        # invariant 1: structural validator clean
        flags = vp.check(p)
        fails(bool(flags), f"[{name}] structural flags: {flags}", errs)
        idn = p["identity"]; bg = p["background"]
        # invariant 2: tier x education
        bad_edu = TIER_EDU.get(idn.get("occupation_tier"), set())
        fails(idn.get("education") in bad_edu,
              f"[{name}] tier {idn.get('occupation_tier')} has education {idn.get('education')}", errs)
        # invariant 3: childless ⇒ no child reference
        if bg.get("children") == 0:
            blob = json.dumps({k: p.get(k) for k in CHILD_SCOPE}).lower()
            fails(bool(CHILD.search(blob)),
                  f"[{name}] childless persona references children", errs)
        # invariant 4: male ⇒ no she/her
        if idn.get("gender") == "M":
            blob = json.dumps({k: p.get(k) for k in GENDER_SCOPE}).lower()
            fails(bool(SHE.search(blob)),
                  f"[{name}] male persona has she/her in free text", errs)
        # invariant 5: schema complete
        missing = [k for k in vp.REQ if k not in p]
        fails(bool(missing), f"[{name}] missing schema fields {missing}", errs)
        # invariant 6: decision_model sane
        dm = p.get("decision_model")
        fails(dm is None, f"[{name}] no decision_model", errs)
        if dm:
            pr = dm.get("prospect", {})
            lam = pr.get("loss_aversion_lambda")
            fails(not (isinstance(lam, (int, float)) and 1.0 <= lam <= 3.6),
                  f"[{name}] loss_aversion_lambda out of range: {lam}", errs)
            g = pr.get("prob_weight_gamma")
            fails(not (isinstance(g, (int, float)) and 0 < g <= 1),
                  f"[{name}] prob_weight_gamma out of range: {g}", errs)
        if errs and len(errs) > 50:
            break
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=900000)
    a = ap.parse_args()

    print("L0 invariant suite")
    print("-" * 64)
    n_neg, neg_errs = test_negative_corpus()
    print(f"A. anti-rot negative corpus: {n_neg} fixtures, "
          f"{'PASS' if not neg_errs else f'FAIL ({len(neg_errs)})'}")
    for e in neg_errs[:20]:
        print("   ! " + e)

    prop_errs = test_property_based(a.n, a.seed)
    print(f"B. property-based: {a.n:,} fresh personas, "
          f"{'PASS' if not prop_errs else f'FAIL ({len(prop_errs)})'}")
    for e in prop_errs[:20]:
        print("   ! " + e)

    ok = not neg_errs and not prop_errs
    print("-" * 64)
    print("RESULT:", "PASS — all invariants hold" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
