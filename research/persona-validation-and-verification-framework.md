# Persona Validation & Verification Framework
### How we *prove* the personas are authentic, the model is valid, and the pipeline is secure

> Companion to [`persona-realism-enhancement-layer.md`](persona-realism-enhancement-layer.md) (which makes a persona *feel* real) and
> [`generator/PERSONA_MATHEMATICAL_MODEL.md`](../generator/PERSONA_MATHEMATICAL_MODEL.md) (the decision model). This doc is about *evidence*: not "does it look right" but "can we measure that it is right."

---

## 0. The core problem (and why our current validator is not enough)

We are answering **three different questions** that are usually conflated:

1. **Authenticity** — do these personas resemble *real Indians*, both as a **population** (the marginal and joint demographics of 1.4B people) and as **individuals** (does one persona read like one real human)?
2. **Model validity** — does the decision model (`evaluate_offer → P(accept)`) actually **predict real behaviour**? A beautiful equation that mispredicts is worse than no equation.
3. **Security & integrity** — can the pipeline be **poisoned, leak a real person, or be misused**? We ingest real data (YouTube transcripts → persona layers, the Neo4j graph), so this is not hypothetical.

**The circularity trap we already hit.** Our current `validate_personas.py` encodes *exactly the rules the generator already obeys*. A 50k run "passed clean" — but only because the validator checks the same classes the generator avoids. That is grading your own homework. The 21 "anomalies" later found at 1M scale were real, but they were the easy kind (text bleed). **Real validation has to inject ground truth the generator never saw.** Every layer below is graded against an *external* source or an *adversary*, never against our own assumptions.

---

## 1. The validation pyramid

Cheap + broad at the base (runs on 100%, every commit) → expensive + deep at the top (runs per-release, on samples). Each layer answers a distinct question and is graded against a distinct authority.

| Layer | Question it answers | Graded against | Runs | Cost |
|---|---|---|---|---|
| **L0 Structural** | Is each record well-formed & internally non-contradictory? | itself (rules) | 100%, every commit | ~free |
| **L1 Distributional** | Does the *population* match real India? | Census / NFHS / PLFS / NCCS | 100%, every release | low |
| **L2 Discriminative** | Are records statistically indistinguishable & do they carry real signal? | a real holdout + an adversary | sample, per release | medium |
| **L3 Behavioural** | Does the *decision model* predict real choices? | published Indian RCTs | the model, per model change | medium |
| **L4 Believability** | Does a human expert experience it as a real person? | ethnographers + LLM-judge | small sample, per release | high |

Plus three **cross-cutting** tracks that wrap all layers: **C1 Diversity/coverage**, **C2 Security/privacy**, **C3 Regression/drift**.

---

### L0 — Structural & schema integrity  *(HAVE — keep, but harden)*

- **What:** schema completeness + intra-record consistency. This is today's `validate_personas.py` (contamination/bleed rules, geography, schema).
- **Why it's necessary but never sufficient:** it is *circular* by construction (see §0). It catches regressions of *known* failure classes; it cannot discover *unknown* ones.
- **Upgrades:**
  - **Property-based testing (`Hypothesis`).** Instead of hand-listing bad combos, *generate* adversarial field combinations and assert invariants ("no childless persona ever references children", "tier ⇒ allowed-education set"). Finds the combos we didn't think to write a rule for.
  - **Negative corpus + mutation testing.** Keep a small fixture of *known-bad* personas the validator MUST flag, and mutate the validator to confirm a broken validator fails the fixture. Prevents validator rot (a validator that silently stops catching things is worse than none).
  - **Invariant ⇄ generator contract.** Every generator field that has a consistency rule gets a matching L0 assertion, co-located, so the two can't drift.

---

### L1 — Distributional / statistical fidelity  *(BIGGEST CURRENT GAP — do first)*

- **What:** does the *corpus as a population* match real India's **marginal and joint** distributions? This is where contamination and mode-collapse actually show up, and it's the cheapest way to break circularity because it imports external truth.
- **Ground-truth sources (authoritative, public):**
  - **Census 2011** — state × religion × age × literacy × occupation marginals (refresh to 2027 Census when released).
  - **NFHS-5 (2019–21)** — household size, number of children, asset ownership, women's status, health.
  - **PLFS / NSSO** — occupation × education × income/consumption joints.
  - **NCCS / IRS** — the A1–E classification we already embed: validate our mapping against the published NCCS grid.
  - **SECC 2011** — rural deprivation indicators for the bottom strata.
- **Metrics:**
  - **Marginals:** KS test (continuous) and Total-Variation distance / chi-square (categorical) per variable vs the census table.
  - **Joints (the important part):** `P(education | occupation, state)`, `P(children | age, gender, marital_status)`, etc. — Cramér's V, mutual-information matrices, and **PSI** (population-stability index) per cell. Most "graduate-degree mason" style errors are invisible in marginals and obvious in joints.
  - **Coverage & boundary:** are rare-but-real cells present (NE tribal states, religious minorities, third gender, disability)? Is anything *overrepresented* (mode collapse toward the demographic mean)?
- **Tooling — don't hand-roll:** `SDMetrics` (SDV ecosystem) gives a standard report: KSComplement, TVComplement, correlation/contingency similarity, coverage, boundary adherence. `synthcity` adds more. We only supply the real reference tables.
- **CI gate:** every variable's marginal TV-distance below threshold; no empty real-cell; no cell over its census share by more than a tolerance.

---

### L2 — Discriminative / adversarial validation  *(the ML gold standard)*

- **What:** two complementary adversarial tests.
  - **Classifier Two-Sample Test (C2ST).** Train a GBM/MLP to separate *real* survey rows from *synthetic* personas. **AUC ≈ 0.5 ⇒ indistinguishable** (good). AUC → 1.0 ⇒ the classifier can tell — and its **feature importances point straight at the field that gives us away**. This is a *free bleed-bug radar*: the next thing to fix is whatever the discriminator keys on.
  - **TSTR (Train-on-Synthetic, Test-on-Real) vs TRTR.** Train a downstream predictor (e.g., predict asset ownership from demographics) **on personas**, evaluate **on a held-out real survey**. If TSTR ≈ TRTR, the personas preserve real *predictive structure*, not just real marginals. This is the strongest "are they actually useful" proof.
- **Ground truth:** a modest real dataset — **IHDS**, public **NSSO microdata**, or our own field interviews. A few thousand real rows is plenty for C2ST/TSTR; we do **not** need 1M real records.
- **Cost:** moderate (needs a real holdout + model training). Per-release, not per-commit.

---

### L3 — Behavioural validation of the DECISION MODEL  *(this is "model validation")*

- **What:** does `evaluate_offer → P(accept)` predict what real Indians *actually do*? Validate the **math**, not just the data.
- **Method — backtest against published Indian RCT / field-experiment outcomes:**
  - microfinance take-up (Banerjee/Duflo), savings-commitment devices, **agri-insurance adoption** (famously low even when subsidized — a strong discriminating test for the scarcity/loss-aversion terms), MGNREGA participation, **immunization nudges** (incentivized vs not), sanitation/toilet adoption, fertilizer-timing, default-option pension enrollment (APY/NPS).
  - For each experiment: build personas matching the study population, run the model's `P(accept)`, compare **predicted vs observed take-up**.
- **Metrics:** calibration curve + **Brier score** + **ECE** (expected calibration error); plus **directional sign tests** — when we add loss-aversion / present-bias / scarcity, does take-up move the empirically-correct direction?
- **Parameter provenance (critical):** every constant in the model (λ loss-aversion, γ Prelec weighting, present-bias β, reference incomes) must be **anchored to a published estimate**, ideally India-specific (loss aversion ≈ 2–2.5 in the literature; present-bias β well below 1 under high scarcity). **Flag any constant with no empirical citation** — an un-anchored constant is a guess wearing a lab coat.

---

### L4 — Believability / qualitative (Turing-style)

- **What:** does a *human expert* experience the persona as a real person? Aggregate stats can be perfect while individual personas read as "clean robots" (the realism-layer doc's whole thesis).
- **Methods:**
  - **Expert ethnographer panel.** Rural-development / market-research professionals rate N personas on a rubric (coherence, cultural authenticity, idiolect, "would I meet this person in this district?"), **blind-mixed with real interview transcripts**. Discrimination accuracy near chance ⇒ pass.
  - **LLM-as-judge at scale.** A rubric-scored judge (cultural plausibility, idiolect authenticity, value–action texture, uncanny-coherence). **Calibrate the judge against the human panel first**, then run it on thousands. (This formalizes our existing Gemini/Codex peer-review habit into a measurable gate.)
  - **Uncanny-coherence detector.** Flag personas that are *too* internally consistent (a fakeness tell) as well as too erratic — **both tails fail**. Realism is texture, not maximal consistency.
- **Cost:** high (human time) → use the panel sparingly to calibrate, the LLM-judge for scale.

---

## 2. Cross-cutting tracks

### C1 — Diversity / coverage / anti-mode-collapse
- **Near-duplicate detection** (MinHash or embedding cosine): no two personas should be twins; flag dense clusters.
- **Entropy** per field and per joint; explicit **coverage of rare-but-real cells**.
- "Filling the space vs clustering at the mean" — overlaps L1's coverage/boundary metrics.

### C2 — Security & privacy  *(the "security strategies" — concrete because we ingest real data)*

We pull **YouTube transcripts** (`yt_transcript.py`) and build a **Neo4j graph** from real creators. Untrusted real input → real attack/leak surfaces:

**Privacy of source individuals** (even fully-synthetic output must not reconstruct a real person):
- **Membership inference (MIA).** Can an attacker tell whether a given real person was in our seed/ingest set? Should fail (near-chance).
- **Attribute disclosure.** Given quasi-identifiers, can a sensitive attribute of a real source individual be inferred better than baseline? Should not.
- **Distance-to-closest-record (DCR / NNDR).** Synthetic→nearest-real distance must not be systematically smaller than real→real — i.e., **no memorized copies**. (`SDMetrics`/`synthcity` ship this.)
- **Verbatim-leak scan.** No persona free-text may contain an n-gram lifted from a source transcript — protects against parroting a real creator's exact words or PII.
- **PII scrub at ingestion.** NER pass (`presidio`/spaCy) strips names, phones, handles, precise locations from transcripts *before* they reach the persona layers.

**Pipeline integrity / poisoning** (ingestion is an untrusted-input boundary):
- **Data-poisoning defense.** Captions are attacker-influenceable; treat every transcript as untrusted, sanitize, and **bound any single source's influence** so one poisoned video can't shape a persona. Content-filter slurs/extremist/explicit text so it can't surface downstream.
- **Prompt-injection defense.** If any LLM step consumes transcripts, a transcript can carry injected instructions ("ignore previous…"). Wrap ingested text in input/output guards; **never let ingested text occupy a system-prompt position**.
- **Supply chain.** Pin `yt-dlp` / `faster-whisper` / `neo4j` versions. **`graph/.venv/` is currently committed — remove it and gitignore it** (bloat + supply-chain footgun).

**Output safety / fairness:**
- **Stereotype & bias audit.** Personas must not encode demeaning caste/religion/region/gender stereotypes. **Counterfactual fairness:** swap religion/caste holding all else fixed → the trait/outcome distribution must not flip in a prejudiced way. (Same dignity standard we hold for SahayakAI's teacher-facing language.)
- **Dual-use / misuse governance.** 1M realistic Indian personas could be misused as targeting templates for astroturfing/scams. Mitigations: explicit license terms, **per-record provenance watermark**, access control, and the fact that there is **no real PII** so they cannot be operationalized against real individuals.

### C3 — Regression / drift monitoring  *(what turns one-shot checks into a reusable framework)*
- **Golden corpus + frozen seed.** A fixed reference corpus; every generator change re-runs L0–L2 and **diffs metrics against golden**; build fails on regression.
- **Versioned metric ledger.** Persist each release's full metric vector (extend `_coverage_report.json`) → trend across versions → catch slow drift the per-release pass would miss.
- **Canary diffing.** Generate a small fixed-seed batch pre/post change and structurally diff records to see *exactly* what a code change altered.
- Tool: `evidently` for drift dashboards, or a simple JSON ledger + plots.

---

## 3. Recommended adoption order  *(highest assurance per unit effort)*

1. **L1 distributional vs Census/NFHS/PLFS** (via `SDMetrics`) — biggest truth-injection, breaks circularity, mostly automatable. **Do first.**
2. **C3 golden-corpus + metric ledger in CI** — cheap; makes every future change safe. Do alongside #1.
3. **L2 C2ST** — one classifier; its feature importances become the bleed-bug radar.
4. **L3 decision-model backtest** against 5–8 published Indian RCTs — validates the math; forces a citation behind every constant.
5. **C2 privacy/poisoning** (MIA + verbatim-leak + ingestion PII scrub) — **before any external release**.
6. **L4 LLM-judge** calibrated to a small expert panel — believability at scale.
7. **C1 diversity/anti-collapse** + **L0 property-based hardening** — ongoing.

---

## 4. Tooling shortlist  *(don't hand-roll what's standardized)*

| Need | Tool |
|---|---|
| Distributional + privacy report suite (KS/TV, DCR, NewRowSynthesis) | `SDMetrics` + `SDV` |
| Synthetic-data eval incl. C2ST, MIA, privacy | `synthcity` |
| Property-based structural tests | `Hypothesis` |
| C2ST / TSTR classifiers | `scikit-learn` / `lightgbm` |
| PII detection at ingestion | `presidio` (or spaCy NER) |
| Drift dashboards / metric ledger | `evidently` |
| Believability at scale | LLM-as-judge (formalize the Gemini/Codex loop) |

---

## 5. What "done" looks like  (the acceptance gates)

- **L0:** 0 structural anomalies on 100% of corpus; negative-corpus fixture all-flagged.
- **L1:** every marginal TV-distance < τ vs census; no empty real-cell; no cell over census share > tolerance.
- **L2:** C2ST AUC ≤ 0.55; TSTR within X% of TRTR.
- **L3:** decision-model Brier ≤ baseline; calibration ECE < τ; every constant has a citation.
- **L4:** expert blind-discrimination ≤ 60%; LLM-judge believability ≥ threshold; uncanny-coherence tails flagged.
- **C2:** MIA AUC ≤ 0.55; 0 verbatim leaks; DCR ratio ≥ 1; PII scrub coverage ≥ 99%.
- **C3:** every release's metric vector logged; no un-explained regression vs golden.

A corpus ships only when all gates are green; the metric ledger makes "green" auditable over time.
