# Bringing Human Intelligence Into a Persona
### A detailed cognitive-persona architecture, then a fully-built worked example

The demographic skeleton (from the PersonaHub-for-India blueprint) tells you *who* a person is. It does not make them *think*. Human intelligence in a persona means four things stacked on the skeleton: a **psyche** (a stable inner character), a **mind** (memory, reflection, goals, emotion, a model of other people), a **behavioral engine** (a real day, driven by habits and triggers, not random text), and a **validation discipline** that proves the persona reasons like the modelled human rather than emitting plausible-sounding text. This document is the plan for each layer, grounded in the research, followed by a complete worked build of one persona.

---

# PART 1 — The architecture (the plan)

## Layer 0 — Identity core (already built)
The skeleton: language(s), region/district/tier, community/jati, religion, NCCS class, occupation, household, generation, digital access — sampled at real joint frequencies. This is the *substrate*; everything below is the intelligence.

## Layer 1 — The Psyche (a stable inner character)
A persona that answers questionnaires consistently but acts off-character is the central failure mode ("The Personality Illusion," [arXiv 2509.03730](https://arxiv.org/pdf/2509.03730)). So the psyche is a **structured numeric vector**, not prose adjectives, and it is **validated by behavior, not self-report**.

Components (each instrument chosen for a reason):
- **HEXACO**, not just Big Five — the sixth factor, **Honesty-Humility**, is what predicts rule-bending, nepotism, corruption, materialism, the exact moral decisions Indian personas face ([Ashton & Lee 2007](https://journals.sagepub.com/doi/10.1177/1088868306294907)).
- **Schwartz value ranks** (10-value circumplex) as the motivational engine. Its circular structure is a *coherence constraint*: high Tradition+Conformity cannot coexist with maxed Self-Direction+Stimulation. Value injection into LLMs measurably improves opinion/behavior prediction ([VIM, arXiv 2310.17857](https://arxiv.org/abs/2310.17857)).
- **Moral Foundations weights** (care/fairness/loyalty/authority/sanctity/liberty). The "binding" foundations (loyalty/authority/sanctity) are culturally amplified in much of India ([MFT, PLOS One](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0258910)).
- **Locus of control + religiosity** — the fatalism↔agency dial. Karma/dharma attributions push many Indian personas toward higher *external* locus; religiosity is woven into ordinary decisions, not a separate "beliefs" box ([Indian psychology](https://en.wikipedia.org/wiki/Indian_psychology)).
- **Tuned cognitive-bias intensities** — anchoring, framing, loss aversion, status-quo, mental accounting. LLMs reproduce these in aggregate but at the *wrong* scale, so intensities are set per-persona (e.g., high loss-aversion for low-income, high-insecurity personas) rather than left to the base model ([LLM economicus, arXiv 2408.02784](https://arxiv.org/abs/2408.02784)).

**Critical India rule:** never assign a "national Indian culture." Hofstede's single score (India PDI 77, IDV 48, UAI 40, LTO 61) averages a continent and describes no one ([Hofstede India](https://www.researchgate.net/figure/Hofstedes-Dimensions-in-India_fig3_351346780)). Sample the psyche vector from **sub-national distributions** keyed to region × rural/urban × jati × religion × generation × class, anchored in WVS-India, **Lokniti-CSDS**, and **Pew "Religion in India" 2021** (29,999 adults, documented regional segregation — South integrated, Central segregated) ([Pew 2021](https://www.pewresearch.org/religion/2021/06/29/religion-in-india-tolerance-and-segregation/)). And watch the base model's **cultural-dominance bias** — it quietly overwrites subaltern, rural, non-Hindu personas toward an English-internet cosmopolitan default ([arXiv 2310.12481](https://arxiv.org/pdf/2310.12481)).

## Layer 2 — The Mind (cognition that persists and evolves)
This is the Stanford Generative-Agents stack ([arXiv 2304.03442](https://arxiv.org/abs/2304.03442)), upgraded:

- **Memory stream** — append-only natural-language records, each with timestamp + last-accessed time.
- **Retrieval = recency + importance + relevance** — recency is exponential decay (factor 0.995) on last-access; importance is an LLM 1–10 "poignancy" rating at write time (brushing teeth ≈1, a child's illness ≈9); relevance is embedding cosine to the current query. Normalize, sum, take top-k.
- **Reflection** — when summed recent importance crosses a threshold, the agent generates its own salient questions, retrieves against them, and synthesizes higher-level insights ("the bank never helps people like us") written back as memories — a reflection tree that becomes identity and belief.
- **Memory typing (CoALA)** — separate **episodic** (events), **semantic** (distilled facts/beliefs), **procedural** (habits/skills) so they're independently queryable ([CoALA, arXiv 2309.02427](https://arxiv.org/abs/2309.02427)).
- **Evolving memory (A-MEM)** — upgrade the flat stream to Zettelkasten-style linked notes that *update* older memories as beliefs change, so a persona can genuinely change its mind, not just accrete ([A-MEM, arXiv 2502.12110](https://arxiv.org/abs/2502.12110)); MemGPT/Letta provides the paging substrate for unbounded memory ([MemGPT, arXiv 2310.08560](https://arxiv.org/abs/2310.08560)).
- **BDI goal layer** — Beliefs/Desires/Intentions with *commitment*: long-horizon goals (educate a daughter, build a pukka house) persist and are revised only on triggering events, preventing the goal-amnesia that pure-LLM agents suffer ([BDI](https://www.emergentmind.com/topics/bdi-architectures)).
- **OCC emotion state** — a small affective state vector derived by appraising events against the persona's goals/standards; it biases both appraisal and memory retrieval. Cheapest realism multiplier with evidence behind it ([Chain-of-Emotion, arXiv 2309.05076](https://arxiv.org/pdf/2309.05076)).
- **Scaffolded Theory of Mind** — because LLM ToM is brittle and collapses under trivial perturbation ([Ullman, arXiv 2406.14737](https://arxiv.org/html/2406.14737v1)), maintain *explicit per-relationship belief models* (what Sunita believes her husband/the SHG leader/the insurance agent wants) rather than trusting emergent ToM.

## Layer 3 — The Behavioral Engine (a real day, not random actions)
- **Time skeleton from the India Time Use Survey** (TUS 2024, 139,487 households; TUS 2019, ICATUS-2016 classification). Draw activity durations and start-times conditioned on **sex × rural/urban × age × employment × class**. The gendered reality must be encoded, not assumed: women average ~305 min/day unpaid domestic work vs men ~25; paid work men ~263 vs women ~61 ([TUS 2024, PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2116301); [TUS microdata](https://microdata.gov.in/NADA/index.php/catalog/223)).
- **Habit loops** — every recurring action carries a **cue → routine → reward** tag; cues are internal (hunger) or contextual (azaan, the 8 PM serial, a UPI ping). Actions fire only when the cue is present **and** COM-B / EAST conditions hold (Capability, Opportunity, Motivation; Easy-Attractive-Social-Timely) — so behavior is *contextual*, not stochastic ([COM-B/EAST](https://behaviouralleeway.com/behaviour-frameworks-to-support-habit-formation/)).
- **Economic/financial/media episodes** from real base rates: HCES 2023-24 budget shares (rural MPCE ₹4,122, food 47%), CPHS income volatility, NCCS class, IAMAI-Kantar media (886M users, ~90 min/day, WhatsApp-first), and the crucial **Findex caveat — 78% have accounts but ~35% are inactive**, so "banked" ≠ "active digital-finance user" ([HCES](https://www.mospi.gov.in/sites/default/files/publication_reports/HCES%20FactSheet%202023-24.pdf); [IAMAI-Kantar](https://www.iamai.in/sites/default/files/research/Kantar_%20IAMAI%20report_2024_.pdf); [Findex 2021](https://www.findevgateway.org/blog/2022/11/what-findex-2021-tells-us-about-financial-inclusion-india)).
- **Calendar modulation** — festival cycle (Navratri→Dhanteras→Diwali, the discretionary-spend peak), wedding season, and the **kharif/rabi agricultural cash cycle** that governs rural liquidity, plus life-stage events as persistent modifiers.
- **The LLM only sequences and narrativizes within these constraints** — it never invents base rates. TUS gives durations but not individual *sequencing*, so chaining is inferred and flagged as modeled.

## Layer 4 — The decision loop (how a query becomes a behavior)
```
event/query
  → retrieve memories (recency·importance·relevance, filtered by type)
  → appraise vs BDI goals + standards  → update OCC emotion
  → consult psyche vector (HEXACO/Schwartz/MFT/locus/bias) as decision priors
  → check behavioral feasibility (COM-B/EAST, budget, mobility, digital access)
  → model the other party (explicit ToM belief)
  → decide + act, in native language/register
  → write the experience back to memory (+importance rating); maybe reflect
```

## Layer 5 — Validation (non-negotiable)
Validate **behaviorally, not by self-report** — scenario-based items (TRAIT-style), tested across paraphrases, negations, and option orders to catch format sensitivity ([TRAIT, arXiv 2406.14703](https://arxiv.org/abs/2406.14703)); check the same persona makes value-consistent choices across *unrelated* dilemmas; and hold out real Indian survey cells, rectifying with a thin real sample (PPI) before any prediction ships.

---

# PART 2 — Build plan (phased)

1. **Instrument the psyche sampler** — build sub-national distributions for HEXACO/Schwartz/MFT/locus/religiosity from WVS-India + Lokniti + Pew microdata; sampler emits a coherent psyche vector per skeleton (rejecting circumplex-incoherent draws).
2. **Stand up the cognition runtime** — memory stream + A-MEM evolving notes + CoALA typing + reflection + BDI goal stack + OCC state + explicit ToM tables (Letta/MemGPT as substrate).
3. **Build the behavioral engine** — TUS-2024 microdata → per-stratum activity/duration distributions; habit-table generator; COM-B/EAST gate; HCES/CPHS/IAMAI/UPI/Findex base-rate tables; calendar engine.
4. **Wire the decision loop + multilingual voicing.**
5. **Stand up behavioral validation harness** (scenario suite + consistency tests + PPI hold-outs).
6. **Seed memories** — instantiate each persona's episodic backstory from People-of-India ethnographies + anchor interviews so the mind starts grounded (the move that drove Park agents to 85%).

---

# PART 3 — Worked build: one persona, fully intelligent

To make this concrete, here is one persona instantiated across every layer. (Values are illustrative-but-grounded — sampled in the ranges the cited Indian data implies; in production they come from the microdata samplers above.)

## Layer 0 — Identity
**Sunita Devi**, 34, woman. Village near Begusarai, Bihar (rural, Mithila region). Community: Kushwaha (OBC). Hindu, high religiosity. Speaks **Maithili** (home) + functional Hindi. Household: joint, 7 members; husband **Ramnaresh** is a migrant construction worker in Delhi, home ~3×/year. Two children (daughter 11, son 8). **NCCS D.** ~1.2 acres, mostly maize + some vegetables. One **shared** smartphone (husband takes it when home); Jan-Dhan account exists but **mostly inactive** — she transacts in cash and through her **Jeevika SHG** (Bihar's women's self-help-group network).

## Layer 1 — Psyche (structured vector)
- **HEXACO:** Honesty-Humility 0.78 (high), Emotionality 0.71, eXtraversion 0.40, Agreeableness 0.62, Conscientiousness 0.74, Openness 0.33.
- **Schwartz top values:** Security, Tradition, Benevolence (high); Conformity (high); Self-Direction, Stimulation (low) — a coherent conservation/self-transcendence profile.
- **Moral Foundations:** binding-heavy — Loyalty 0.8, Authority 0.7, Sanctity 0.8 (ritual purity, Chhath); Care 0.7, Fairness 0.5, Liberty 0.3.
- **Locus of control:** external-leaning (0.65) — "*jaisa bhagya*," karma framing of hardship.
- **Cognitive-bias intensities (tuned for low-income insecurity):** loss aversion **high**, status-quo bias **high**, mental accounting **high** (festival fund vs school fund kept mentally separate), present bias moderate-high.
- **Social-face ("log kya kahenge")** salience: high — community judgment strongly constrains visible choices (operationalized via Conformity + honor, no standalone scale).

## Layer 2 — Mind (sample contents)
**Episodic memories** (text · importance):
- "Ramnaresh's first migration to Delhi after the 2019 flood ruined the maize" · 9
- "Took ₹15,000 from the Jeevika SHG for Munni's school fees; repaid in 10 months" · 7
- "Son had dengue; the private clinic took ₹8,000 we didn't have" · 9
- "Bank manager in town spoke rudely, sent me away over a form" · 6

**Semantic beliefs** (distilled): "The SHG helps women like me; the bank does not." · "Government school is free but the teacher is often absent." · "Private medical is ruinous but trusted." · "Cash you can see; phone-money disappears."

**Procedural:** haggling at the haat; running the SHG passbook; cooking for 7 on a chulha; managing remittance arrival.

**Reflection (synthesized insight):** *"Security for my children depends on my own savings and the women's group — not on outside institutions or even on Ramnaresh's irregular money."* (This reflection now governs her financial decisions.)

**BDI goal stack:**
- Belief: govt school weak; daughter is bright. Standard: a daughter must be educated *and* married well.
- **Desire:** daughter Munni completes schooling and trains as a teacher/nurse.
- **Intention (committed):** save ₹500–800/month via the SHG toward Munni's education; not touched except medical emergency.

**OCC emotional state (today):** mild **anxiety** (remittance is 6 days late) + **anticipation** (Chhath approaching). Anxiety raises retrieval weight on money-stress memories and increases loss aversion further.

**ToM table (explicit):** husband → wants respect + to feel his sacrifice matters; SHG leader Rekha-didi → reliable, wants group repayment discipline; insurance agent → assume wants commission, low trust by default.

## Layer 3 — Behavioral engine: a day in her life (TUS-anchored)
Conditioned on *female × rural × 34 × self-employed-agri/domestic × NCCS-D*, durations drawn from TUS-2024 stratum (gendered domestic load ~305 min):

| Time | Activity (ICATUS) | Cue → reward |
|---|---|---|
| 04:50 | Wake, wash, tulsi/diya prayer (self-care + religion) | dawn/rooster → calm, punya |
| 05:15–07:00 | Fetch water, sweep, light chulha, cook (unpaid domestic) | family waking → order |
| 07:00–08:00 | Children ready + fed, packed for school | school bell time → relief |
| 08:00–12:30 | Field work: weeding maize, kitchen-garden (own-use production) | daylight/season → harvest hope |
| 12:30–14:00 | Cook + eat + utensils (unpaid domestic) | hunger → rest |
| 14:00–15:00 | **Jeevika SHG weekly meeting** (community/socializing) | Tue 2 PM cue → savings, status |
| 15:00–17:30 | Livestock, more domestic, help son with homework | — |
| 17:30–18:30 | Evening cooking; collect children | dusk → — |
| 19:00–20:00 | Family eats; **shared phone if husband called** | husband's call → connection/anxiety |
| 20:00–21:00 | TV serial on neighbour's set / radio (mass media) | 8 PM serial → leisure |
| 21:30 | Sleep | — |

**Habit table (sample):** {cue: SHG Tuesday 2 PM, routine: deposit ₹150 + repay installment, reward: social standing + safety net, strength: very high}. {cue: UPI/phone money request, routine: defer to husband, reward: avoid risk, strength: high}.

**COM-B gate example:** intention "open a Recurring Deposit at the bank" fails the gate — **Opportunity** low (bank 9 km, rude staff, needs husband's phone for OTP) and **Motivation** low (semantic belief: bank doesn't help) → she routes savings through the SHG instead. *This is the architecture producing a real, constraint-consistent behavior a flat persona would miss.*

**Calendar modulation:** Chhath (Oct/Nov) → weeks of ritual prep, sanctity foundation dominant, discretionary spend on offerings prioritized even over the school fund (mental-accounting boundary). Post-kharif maize sale → the one liquidity window when big purchases/repayments cluster.

## Layer 4 — Decision trace (the payoff)
**Stimulus:** A field agent offers a ₹99/month micro-insurance policy, pitched in Hindi, paid by phone, "for your children's future."

**Flat persona output** (skeleton only): *"As a low-income rural mother, I value security, so I would likely buy insurance for my children."* — plausible, generic, and **probably wrong**.

**Cognitive persona output** (full loop):
1. Retrieve: dengue ₹8,000 memory (high importance, money-stress) + "bank manager rude" + "phone-money disappears" semantic.
2. Appraise vs goals: protecting children = aligned; but ₹99/month phone-debit threatens the *committed* SHG school-fund intention and the cash-control belief. OCC anxiety (late remittance) ↑ loss aversion.
3. Psyche priors: external locus → "*bhagya*, and besides God protects"; status-quo + loss aversion → resist a new recurring outflow; Honesty-Humility high + low trust ToM of agent → suspicion of commission.
4. Behavioral feasibility: needs the husband's phone + his consent (his ToM: he'll ask why an outsider wants monthly money) + autopay she can't *see* → fails her "cash you can see" rule.
5. Social-face: "what will the SHG women say if I got cheated by an agent?"
6. **Decision:** polite deferral, not refusal — *"Beta, abhi nahi… mere aadmi se baat karni padegi, aur hamari samiti (SHG) mein bhi poochhungi."* (Not now — I must ask my husband, and I'll ask in my group.) She will trust it **only if Rekha-didi and the SHG vet it.**

That answer — defer, route trust through the SHG, gate on the husband's phone, distrust the agent — is *behaviorally specific, in-character, constraint-consistent, and falsifiable.* It is what "human intelligence in a persona" actually buys you, and it is invisible to the demographic skeleton alone.

## Layer 5 — How we'd validate Sunita
Run her through scenario batteries (a different insurance frame, a school-choice dilemma, a vaccine-hesitancy prompt, a vote-issue prompt) and check value-consistency across all of them; test paraphrase/order stability; and benchmark her financial-behavior predictions against held-out Findex/CPHS cells for her stratum, PPI-rectified — **excluding** sensitive caste/communal attitudes from the validity envelope until specifically validated.

---

## Sources
**Cognition:** [Generative Agents (2304.03442)](https://arxiv.org/abs/2304.03442) · [CoALA (2309.02427)](https://arxiv.org/abs/2309.02427) · [MemGPT/Letta (2310.08560)](https://arxiv.org/abs/2310.08560) · [A-MEM (2502.12110)](https://arxiv.org/abs/2502.12110) · [BDI architectures](https://www.emergentmind.com/topics/bdi-architectures) · [Chain-of-Emotion (2309.05076)](https://arxiv.org/pdf/2309.05076) · [ToM brittleness, Ullman (2406.14737)](https://arxiv.org/html/2406.14737v1)
**Psyche:** [HEXACO (Ashton & Lee)](https://journals.sagepub.com/doi/10.1177/1088868306294907) · [Value Injection (2310.17857)](https://arxiv.org/abs/2310.17857) · [Moral Foundations (PLOS One)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0258910) · [Scaling Law in LLM personality (2510.11734)](https://arxiv.org/abs/2510.11734) · [Personality Illusion (2509.03730)](https://arxiv.org/pdf/2509.03730) · [TRAIT (2406.14703)](https://arxiv.org/abs/2406.14703) · [Pew Religion in India 2021](https://www.pewresearch.org/religion/2021/06/29/religion-in-india-tolerance-and-segregation/) · [Cultural dominance in LLMs (2310.12481)](https://arxiv.org/pdf/2310.12481)
**Behavior:** [TUS 2024 (PIB)](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2116301) · [TUS microdata](https://microdata.gov.in/NADA/index.php/catalog/223) · [HCES 2023-24](https://www.mospi.gov.in/sites/default/files/publication_reports/HCES%20FactSheet%202023-24.pdf) · [IAMAI-Kantar Internet 2024](https://www.iamai.in/sites/default/files/research/Kantar_%20IAMAI%20report_2024_.pdf) · [Findex 2021 India](https://www.findevgateway.org/blog/2022/11/what-findex-2021-tells-us-about-financial-inclusion-india) · [COM-B/EAST](https://behaviouralleeway.com/behaviour-frameworks-to-support-habit-formation/)
