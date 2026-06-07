# Persona Validation Suite

Stdlib-only implementation of the validation pyramid from
[`research/persona-validation-and-verification-framework.md`](../research/persona-validation-and-verification-framework.md).
No third-party dependencies (matches the generator's stdlib-only design; works on Python 3.14).

## One command

```bash
python3 validation/run_validation.py personas/ --reference reference/census_2011.json
```

Runs every layer, prints a dashboard, and appends a versioned metric vector to
`personas/_validation_ledger.jsonl` (drift tracking). Exit code = number of failed gates.

Add `--fast` for smaller samples, `--real holdout.jsonl` to enable the L2 C2ST,
`--no-ledger` to skip the ledger append.

## Layers

| Layer | Script | What it proves | Needs |
|---|---|---|---|
| **L0 structural** | `generator/validate_personas.py` | each record well-formed & non-contradictory | — |
| **L0 invariants** | `validation/test_invariants.py` | anti-rot (negative corpus) + property-based invariants on fresh personas | — |
| **L1 distributional** | `generator/distribution_report.py` | population matches real India (marginals + joints, TV distance) | `reference/*.json` |
| **L3 decision-model** | `validation/backtest_decision_model.py` | `evaluate_offer` predicts real take-up; directionally monotone | `scenarios_india.json` |
| **C2 fairness** | `validation/fairness_audit.py` | no generator-invented bias; no demeaning stereotypes | — |
| **L2 C2ST** | `validation/c2st.py` | real vs synthetic indistinguishable (AUC≈0.5) | real holdout |

## Running layers individually

```bash
# L0 — structural + invariants
python3 generator/validate_personas.py personas/ --fail-on-any
python3 validation/test_invariants.py --n 5000

# L1 — distribution vs census (marginals now; add joints to reference for hard gates)
python3 generator/distribution_report.py personas/ --reference reference/census_2011.json

# L3 — decision-model backtest (calibration + monotonicity sweeps)
python3 validation/backtest_decision_model.py --samples 300

# C2 — fairness / stereotype audit
python3 validation/fairness_audit.py personas/

# L2 — classifier two-sample test (needs real data; self-tests without it)
python3 validation/c2st.py personas/ --real real_holdout.jsonl
```

## Current status (v1.1 corpus, 1,000,100 personas)

- **L0:** 0 structural anomalies; 13/13 negative fixtures flagged; 5,000 fresh personas clean.
- **L1:** religion TV=0.037, rural/urban TV=0.0015 vs Census 2011 — both PASS. Joints awaiting PLFS/NFHS reference values.
- **L3:** 4/5 scenarios within tolerance, Brier 0.0123; all 4 monotonicity sweeps PASS.
- **C2:** conditional-independence PASS; zero demeaning descriptors.
- **L2:** harness self-test AUC=0.494 (unbiased); awaiting a real holdout for a verdict.

## Maintenance

- **Add a validator rule?** Add a negative fixture: edit `make_negative_corpus.py`, run it, commit `fixtures/negative_corpus.jsonl`. `test_invariants.py` will enforce it forever.
- **Get real ground truth?** Fill `reference/census_2011.json` marginals + joints (PLFS occupation×education, NFHS-5 children×age) — they become hard L1 gates automatically.
- **Get a real survey holdout?** Pass `--real` to enable L2; if AUC>0.6 the top-weighted features tell you exactly which field gives the synthetic data away.

## What still needs real-world data (cannot be faked)

The framework is built; these gates only become *binding* once real data is supplied:
- L1 joint references (PLFS/NFHS cross-tabs)
- L2 a real survey holdout (IHDS / NSSO microdata / field interviews)
- L3 verified take-up figures from the primary RCT papers
- L4 (believability) — human ethnographer panel + calibrated LLM-judge (not yet built)
- C2 privacy (membership-inference, verbatim-leak) — only relevant once real transcripts are ingested via `yt_transcript.py`
