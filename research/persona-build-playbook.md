# The Persona Build Playbook
### One page, build order, data, and gates — consolidated from the full architecture

**The one rule:** build ONE persona end-to-end and validate it before scaling. Vertical slice, not horizontal. Use a real person (e.g., Sunita) as the yardstick. Wire validation in from day one.

---

## Build order (do these in sequence; each has a "done when" gate)

| # | Layer | Build | Grounded in | ✅ Done when |
|---|---|---|---|---|
| 0 | **Skeleton** | One persona's coordinates: language(s), district, community/jati, religion, NCCS, occupation, household, generation, gender, digital access | Census 2011, NFHS-5, PLFS | Coordinates are internally consistent (a real cell, not an impossible permutation) |
| 1 | **Psyche** | Structured vector: HEXACO + Schwartz value ranks + Moral-Foundations weights + locus/religiosity + tuned bias intensities. Traits as **mean + variance**, not points | WVS-India, Lokniti-CSDS, Pew 2021 (sub-national, never "national culture") | Schwartz circumplex is coherent; two same-skeleton personas differ via variance |
| 2 | **Mind** | Memory stream (recency·importance·relevance retrieval) + reflection + CoALA typing (episodic/semantic/procedural) + BDI goal stack + OCC emotion + explicit ToM tables. Memory is **reconstructive** (lossy/mood-gated) | People-of-India + a few anchor interviews to seed episodic backstory | Persona retrieves a relevant memory and a reflection that governs a decision |
| 3 | **Self-story** | 6–10 autobiographical scenes (low/high/turning point), tagged redemption/contamination + agency/communion, above the memory stream | Anchor interviews / ethnography | Persona re-narrates a matching scene to explain a choice ("I've always been the one who…") |
| 4 | **Voice (idiolect)** | Per-persona style profile: base language, code-switch ratio, lexicon/proverbs, honorifics (aap/tum/tu), literacy-driven syntax | Hinglish/code-switch corpora; the persona's own register | Two personas sound like two people in one sentence |
| 5 | **Behavioral engine** | TUS-anchored daily schedule (by sex×rural/urban×age×employment) + habit table (cue→routine→reward) gated by COM-B/EAST + base rates (HCES/UPI/Findex) + calendar modulation | TUS-2024 microdata, HCES 2023-24, IAMAI-Kantar, Findex | A day-in-the-life runs; a decision is gated by real feasibility (budget/mobility/digital access) |
| 6 | **Decision loop** | Wire it: event → retrieve → appraise vs goals → update emotion → psyche priors → feasibility gate → model the other party → act in-voice → write back to memory | — | A query produces a behaviorally specific, in-character, falsifiable decision (not a generic demographic statement) |
| 7 | **Realism layer** (after loop runs) | Add in priority order: dual-process gating · controlled inconsistency + rationalization · physiology→affect state · then social-network contagion + WhatsApp media diet | Lally (habits), interoception, bounded-confidence dynamics, WhatsApp-misinfo research | Persona does something *a little wrong and human* (defers when tired, splurges & justifies, believes/forwards a rumor) |

---

## Data acquisition — pull in this order

1. **Skeleton margins:** Census 2011, NFHS-5 (707 districts), PLFS/NSS — via microdata.gov.in / World Bank Microdata.
2. **Psyche distributions:** WVS-India, Lokniti-CSDS, Pew "Religion in India" 2021 (for sub-national value vectors).
3. **Daily life:** India Time Use Survey 2024 unit-level microdata.
4. **Base rates:** HCES 2023-24 (consumption), Findex 2021 (the 78%-banked/35%-inactive caveat), IAMAI-Kantar (media), NPCI (UPI).
5. **Memory seed:** People-of-India ethnographies + a small set of real anchor interviews (the move that drives fidelity).

---

## Validation gates (non-negotiable — these define pass/fail)

- **Behavioral, not self-report.** Test with scenario batteries (TRAIT-style), across paraphrases/negations/option-orders. A persona that passes its personality test but acts off-profile fails.
- **Cross-scenario consistency.** Same persona makes value-consistent choices across *unrelated* dilemmas (insurance, school choice, a vote issue).
- **"Uncanny coherence" check.** Flag personas that are *too* consistent — that's a fakeness tell, not a success.
- **Out-of-distribution, private hold-out.** Benchmark predictions against held-out NFHS/PLFS/CPHS cells the engine never trained on; **PPI-rectify** with a thin real sample. Matching a *published* survey = recall, not prediction.
- **Kill criteria:** if PPI-rectified estimates don't beat the small-human-sample-alone baseline → no value-add. If synthetic subgroup variance <60% of real → homogenization unfixable for tails.

---

## Scale-out trigger
Only after the single persona passes the gates: instantiate the **PersonaHub-for-India** pipeline (Indic Text-to-Persona → Persona-to-Persona expansion → multilingual dedup → distribution-grounding/reweighting to real joint margins). Target the **populated joint cells at real frequency** — low single-digit millions — never the Cartesian product.

## Permanent guardrails
- Sample **sub-nationally**; never assign a "national Indian culture."
- Keep **sensitive caste/religion/communal attitudes outside the validity envelope** until specifically validated.
- Watch the base model's **cultural-dominance bias** (it overwrites rural/subaltern/non-Hindu personas toward a cosmopolitan default).
- A persona is a **falsifiable hypothesis with a confidence interval**, graded forever against reality — not a fact.

---
*Companion docs: cognitive-persona-plan-and-build · persona-realism-enhancement-layer · personahub-for-india-blueprint · india-personas-feasibility-verdict.*
