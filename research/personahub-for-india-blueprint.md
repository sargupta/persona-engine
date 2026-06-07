# PersonaHub-for-India: A Construction Blueprint
### Building India's persona universe across every linguistic, regional, communal, economic and generational spectrum

**The reframe.** India is not a market with segments; it is a civilization of nested, interacting diversities. The single most important design principle: **a persona is a point in a high-dimensional *joint* distribution, not a checklist of independent attributes.** A Tamil Brahmin software engineer in Bengaluru, a Tamil Dalit agricultural labourer in Madurai, and a Tamil Muslim textile trader in Chennai share a language and almost nothing else. If you model the dimensions independently you get cardboard cut-outs; if you model the *joint*, you get India. PersonaHub is the right engine precisely because **Text-to-Persona lets the real combinations emerge from real text** rather than being enumerated by a foreigner's imagination.

**The mistake to avoid.** Do not generate American/Anglophone personas and translate them. A Western-trained LLM has thin, stereotyped Indian priors. The fix is structural: **re-seed PersonaHub from native Indic text**, so personas are born in-language and in-culture.

---

## 1. India's dimensional space (the coordinate system, grounded)

Every persona is a point with coordinates on these axes. The numbers are real and citable — they define the resolution the engine must reach.

| Dimension | Real resolution (sourced) |
|---|---|
| **Language / mother tongue** | Census 2011: **19,569 raw returns → 1,369 mother tongues → 270 (>10k speakers) → 121 languages**; **22 scheduled + 99 non-scheduled** ([India Forum](https://www.theindiaforum.in/article/what-census-obscures)). Plus code-switching & diglossia. |
| **Community (jati) / social group** | Anthropological Survey of India *People of India* project: **4,635 communities** (461 Scheduled Tribes), studied across 4,581 villages, 25k informants, 43 volumes ([People of India / AnSI](https://en.wikipedia.org/wiki/The_People_of_India)). Plus varna category (Gen/OBC/SC/ST). |
| **Religion & sect** | Hindu, Muslim, Christian, Sikh, Buddhist, Jain, others — each with sects/sub-traditions. |
| **Geography / tier** | 28 states + 8 UTs, **700+ districts**, agro-climatic zones, urban tiers (metro / Tier-1 / Tier-2 / Tier-3 / town / village). |
| **Economic stratum** | **NCCS A1–E3 (12 grades)** — the MRSI/MRUC standard, based on chief-wage-earner education × durables owned, unified rural+urban ([MRUC NCCS](https://mruc.net/assets/frontend/new-consumer-classification-system.html)). Plus income decile, landholding, asset profile. |
| **Occupation / vocation** | Agriculture / informal / formal-services / manufacturing / gig / government / professional — incl. the role × department × tenure sub-space. |
| **Life-stage / household** | Age cohort, gender, joint vs nuclear family, marital status, generation (Gen-Z digital native ↔ non-literate elder). |
| **Psychographic / cultural** | Veg/non-veg & regional cuisine, festival calendar, religiosity, media diet, aspiration level, digital access, migration status (native / rural-urban migrant / interstate / diaspora). |

The product is the engine that fills the **populated joint cells** of this space at the real frequencies they occur — not the Cartesian product (which is astronomically large and mostly empty), but the cells India actually contains.

---

## 2. How PersonaHub works (so we can re-target it)

PersonaHub (Tencent AI Lab, *Scaling Synthetic Data Creation with 1,000,000,000 Personas*) has three moving parts ([arXiv 2406.20094](https://arxiv.org/html/2406.20094v1); [repo](https://github.com/tencent-ailab/persona-hub)):

1. **Text-to-Persona** — for arbitrary text, prompt the LLM: *"Who is likely to [read / write / like / dislike] this text?"* → a 1–2 sentence persona. Run over a massive corpus → a vast persona pool.
2. **Persona-to-Persona** — expand each persona along **interpersonal relationships** (a nurse → her patients, colleagues, children). This reaches personas **not well-represented in text** — exactly the offline majority.
3. **Dedup** — MinHash (1-gram, 128-bit signature, threshold 0.9) → then embedding cosine-similarity filter (>0.9 removed). Final pool: **1,015,863,523 personas**, used as *conditioning carriers* to steer downstream generation.

Three things to note: PersonaHub was built for **LLM-training diversity, not behavioral representativeness**; its personas are **English-centric**; and it has **no distribution grounding**. Our adaptation fixes all three.

---

## 3. The PersonaHub-for-India pipeline (six stages)

### Stage 1 — Indic Text-to-Persona (native seeding)
Run Text-to-Persona over **AI4Bharat Sangraha** — the largest cleaned Indic pretraining corpus: **251B tokens across all 22 scheduled languages**, and crucially **"Sangraha Verified" includes OCR from Indic-language PDFs and transcribed Indic audio/video**, not just web text ([Sangraha / IndicLLMSuite](https://github.com/AI4Bharat/IndicLLMSuite)). Supplement with IndicCorp, Varta (Indic news), and regional social/forum text.

- **Prompt in-language**, not English: e.g. *"इस लेख को कौन लिखेगा, पढ़ेगा या पसंद करेगा?"* / *"இந்த உரையை யார் எழுதுவார், படிப்பார்?"* So the persona is born in Marathi/Tamil/Bhojpuri register, carrying native idiom, caste/region markers, and concerns.
- The OCR+ASR streams matter enormously: they capture **vernacular, oral, and print voices that never reach the English web** — the structural antidote to urban-Anglophone skew.

**Output:** a large, *natively Indian* persona pool — but still skewed toward who produces text.

### Stage 2 — Persona-to-Persona into the offline majority, grounded in ethnography
The web/Sangraha under-represents the rural, elderly, women, and low-literacy. Use **relationship expansion** to reach them — and **ground the expansion in the People of India ethnographies** so the relationships are real, not hallucinated.

- From *"a government primary-school teacher in a Bundelkhand village"* → her students, their landless-farmer parents, the ASHA health worker, the husband who migrated to Surat's textile mills, the Bundeli-only-speaking grandmother, the local kirana owner, the Dalit sanitation worker.
- Seed these expansions with the **AnSI 4,635-community profiles** (occupations, kinship, customs, inter-community links) — India's nearest equivalent to the deep-interview grounding that drove Stanford/Park agents to 85%. This is what makes a "Toda pastoralist in the Nilgiris" persona real rather than a stereotype.

**Output:** coverage of the cells the internet cannot see.

### Stage 3 — Multilingual deduplication
Adapt PersonaHub's dedup for a 22-language pool:
- MinHash on normalised text **per script/language**, plus a **cross-lingual embedding** pass (multilingual sentence-transformer / IndicBERT-family) so the *same* persona expressed in Hindi and in Bengali is merged, **but genuinely distinct community personas are not** wrongly collapsed. Tune the cosine threshold per-language (0.9 is too aggressive across scripts).

### Stage 4 — Distribution grounding (turn a diverse pool into a representative population)
This is the Nemotron-Personas move PersonaHub lacks: **reweight/resample the persona pool to match real Indian *joint* margins.**
- Targets: Census 2011 (language × region × religion × caste-category × rural/urban), **NCCS A1–E3** strata, NFHS-5 district demographics/assets, PLFS occupation. 
- Method: iterative proportional fitting / raking **over the persona pool**, fitting *joint* household-and-person margins (not independent marginals — the whole point). Each retained persona carries a **representativeness weight**.
- This converts "1 billion diverse personas that predict nothing" into "N representative personas whose population statistics match real India."

### Stage 5 — Schema enrichment
Promote each persona from a 1–2 sentence blurb to a **structured object** (see §4) carrying its dimensional coordinates + a narrative + decision priors, so it is both queryable (filter the population) and voiceable (simulate responses).

### Stage 6 — Multilingual voicing
Each persona responds **in its own language(s) and register**, modelling code-switching/diglossia explicitly, using Indic-capable models (Sarvam, Krutrim, AI4Bharat IndicTrans/IndicLLM) for high-resource languages with graceful degradation flagged for the long tail. Voicing is *grounded* (fine-tuned on real Indic survey/interview responses) — not prompt-roleplay.

---

## 4. The persona object (concrete schema)

```json
{
  "persona_id": "uuid",
  "narrative": "38-yr-old Lingayat sugarcane farmer near Belagavi; speaks Kannada + market Marathi; joint family of 9; smartphone-second-hand; watches Kannada news + YouTube agronomy; votes local-issue-first.",
  "coordinates": {
    "languages": ["kn", "mr-market"], "script": "Kannada",
    "region": {"state": "Karnataka", "district": "Belagavi", "tier": "rural", "agro_zone": "northern dry"},
    "community": {"jati": "Lingayat", "category": "OBC", "religion": "Hindu-Veerashaiva"},
    "economic": {"nccs": "C2", "occupation": "agriculture-landowning", "landholding_acres": 4, "assets": ["2-wheeler","smartphone","pumpset"]},
    "household": {"age": 38, "gender": "M", "family": "joint", "size": 9, "generation": "millennial"},
    "psychographic": {"diet": "veg", "religiosity": "high", "media": ["kn-tv-news","youtube"], "digital_access": "shared-smartphone", "aspiration": "children-to-govt-jobs"}
  },
  "grounding": {"seed": "sangraha-kn + AnSI-Lingayat-profile", "anchors": ["anchor_4412"], "confidence": 0.71},
  "weight": 0.0000037   // representativeness weight from Stage 4
}
```

---

## 5. Scale, honestly

You do **not** want a vanity billion. You want the **populated joint cells of §1 at real frequency.** Order-of-magnitude: ~270 meaningful mother tongues × ~700 districts × ~12 NCCS grades × ~6 generations × major community/religion groups, pruned to cells that actually exist, lands in the **low single-digit millions of distinct representative personas** — each re-samplable to whatever N a simulation needs. PersonaHub's machinery generates and dedups at this scale trivially (it did 1B); the *art* is Stages 2–4, where India-specific grounding and reweighting happen. **Coverage of real cells beats raw count.**

---

## 6. The one discipline that keeps it real (kept short, because it's non-negotiable)
Diversity ≠ accuracy. After Stages 1–6, the population must be **validated by reweighting against held-out real data** (NFHS/PLFS/Census cells the engine never trained on) and corrected with a thin real sample (prediction-powered inference) before any prediction ships. And sensitive caste/religion/communal attitudes stay outside the validity envelope until specifically validated — the LLM's priors there are biased toward the majority, and that is exactly where India's stakes are highest.

---

## Sources
- [PersonaHub — Scaling Synthetic Data Creation with 1B Personas (arXiv 2406.20094)](https://arxiv.org/html/2406.20094v1) · [repo](https://github.com/tencent-ailab/persona-hub)
- [AI4Bharat Sangraha / IndicLLMSuite (251B tokens, 22 languages)](https://github.com/AI4Bharat/IndicLLMSuite) · [IndicCorp](https://indicnlp.ai4bharat.org/corpora/)
- [Census 2011 linguistic diversity (1,369 mother tongues; 22+99 languages) — The India Forum](https://www.theindiaforum.in/article/what-census-obscures)
- [Anthropological Survey of India — *People of India* (4,635 communities)](https://en.wikipedia.org/wiki/The_People_of_India)
- [NCCS — New Consumer Classification System (MRUC/MRSI)](https://mruc.net/assets/frontend/new-consumer-classification-system.html)
- [Nvidia Nemotron-Personas (distribution-aligned persona generation)](https://huggingface.co/blog/nvidia/nemotron-personas)
- [Generative Agent Simulations of 1,000 People (interview grounding) — arXiv 2411.10109](https://arxiv.org/pdf/2411.10109)
