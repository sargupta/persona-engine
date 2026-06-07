#!/usr/bin/env python3
"""
backtest_decision_model.py — L3 model validation.

Backtests the decision model (persona_math.evaluate_offer) against observed
take-up rates from real Indian field experiments (validation/scenarios_india.json).

For each scenario it builds the decision_model with the scenario's population
params across many RNG seeds, runs evaluate_offer with the offer params, averages
P_accept, and compares to the observed take-up:

  - absolute error |predicted - observed|  (vs per-scenario tolerance)
  - Brier score over all primary scenarios (lower = better calibrated)
  - directional checks: does P move the empirically-correct way across scenarios?

This validates the MATH, not the data. A scenario "passes" if |error| <= tolerance.
Directional checks pass if the sign of the difference matches.

Usage:
  python3 validation/backtest_decision_model.py
  python3 validation/backtest_decision_model.py --samples 400 --json out.json
"""
import argparse, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(HERE), "generator")
sys.path.insert(0, GEN)
import persona_math as pm  # noqa: E402


def predict(pop, offer, samples, seed0):
    """Average P_accept over `samples` RNG draws of the same population."""
    ps = []
    for i in range(samples):
        rng = random.Random(seed0 + i)
        dm = pm.decision_model(
            nccs=pop["nccs"], scarcity=pop["scarcity"], age=pop["age"],
            occupation=pop["occupation"], reflective=pop.get("reflective", 0.45),
            openness=pop.get("openness", 0.5), educated=pop.get("educated", False),
            rural=pop.get("rural", True), prior_precision=pop.get("prior_precision", 0.6),
            rng=rng)
        r = pm.evaluate_offer(
            dm,
            monthly_cost_inr=offer["monthly_cost_inr"],
            benefit_value=offer["benefit_value"],
            prob_benefit=offer.get("prob_benefit", 0.3),
            framing=offer.get("framing", "shield"),
            stakes=offer.get("stakes", 0.6),
            time_pressure=offer.get("time_pressure", 0.4),
        )
        ps.append(r["P_accept"])
    return sum(ps) / len(ps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=os.path.join(HERE, "scenarios_india.json"))
    ap.add_argument("--samples", type=int, default=300)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--json", help="write full results to this path")
    a = ap.parse_args()

    spec = json.load(open(a.scenarios))
    scenarios = {s["id"]: s for s in spec["scenarios"]}
    results = {}
    brier_terms = []

    print("\nL3 decision-model backtest vs Indian field experiments")
    print("=" * 72)
    print(f"{'scenario':<34}{'pred':>7}{'obsv':>7}{'err':>7}  status")
    print("-" * 72)
    for sid, s in scenarios.items():
        pred = predict(s["population"], s["offer"], a.samples, a.seed)
        obs = s["observed_take_up"]
        err = abs(pred - obs)
        tol = s.get("tolerance", 0.2)
        ok = err <= tol
        results[sid] = {"predicted": round(pred, 3), "observed": obs,
                        "abs_error": round(err, 3), "tolerance": tol,
                        "pass": ok, "tier": s.get("tier")}
        if s.get("tier") == "primary":
            brier_terms.append((pred - obs) ** 2)
        print(f"{sid:<34}{pred:>7.3f}{obs:>7.3f}{err:>7.3f}  "
              f"{'OK' if ok else 'FAIL'}")

    print("-" * 72)
    # one-variable monotonicity sweeps (the rigorous directional test)
    print("Monotonicity sweeps (hold all else fixed, vary one param):")
    dir_pass = True
    dir_results = []
    for sw in spec.get("sweeps", []):
        pop = dict(sw["base_population"])
        offer = dict(sw["base_offer"])
        curve = []
        for val in sw["values"]:
            if "vary_population" in sw:
                pop2, offer2 = dict(pop), offer
                pop2[sw["vary_population"]] = val
                p = predict(pop2, offer2, a.samples, a.seed)
            else:
                offer2 = dict(offer)
                offer2[sw["vary"]] = val
                p = predict(pop, offer2, a.samples, a.seed)
            curve.append(round(p, 3))
        if sw["expect"] == "decreasing":
            ok = all(curve[i] >= curve[i + 1] for i in range(len(curve) - 1))
        else:  # increasing
            ok = all(curve[i] <= curve[i + 1] for i in range(len(curve) - 1))
        dir_pass = dir_pass and ok
        dir_results.append({"id": sw["id"], "values": sw["values"],
                            "curve": curve, "expect": sw["expect"], "pass": ok})
        print(f"  {sw['id']:<32} {sw['expect']:<11} {curve}  -> "
              f"{'OK' if ok else 'FAIL'}")

    brier = sum(brier_terms) / len(brier_terms) if brier_terms else None
    n_pass = sum(1 for r in results.values() if r["pass"])
    print("=" * 72)
    if brier is not None:
        print(f"Brier score (primary scenarios): {brier:.4f}  (lower is better)")
    print(f"Scenarios within tolerance: {n_pass}/{len(results)}   "
          f"Directional: {'PASS' if dir_pass else 'FAIL'}")

    out = {"results": results, "directional": dir_results, "brier_primary": brier,
           "n_pass": n_pass, "n_total": len(results), "directional_pass": dir_pass,
           "samples": a.samples}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2)
        print(f"-> {a.json}")

    # Gate: all primary within tolerance AND directional pass.
    primary_ok = all(r["pass"] for r in results.values() if r["tier"] == "primary")
    sys.exit(0 if (primary_ok and dir_pass) else 1)


if __name__ == "__main__":
    main()
