# Infinite-Persona

A system for generating population-scale, cognitively-grounded **synthetic personas of India** for behavioural prediction and research augmentation.

## What's in here
- **`Synthetic_Indian_Personas_Design_Specification.docx`** — the master design specification (23 pages, IEEE references): vision, feasibility, the PersonaHub-for-India generation pipeline, the cognitive architecture, the realism layer, the decision engine (8 literatures of human cognition), data foundation, validation, roadmap, open-source components, and the interim-operations plan. Appendix A is a copy-paste kickoff prompt; Appendix B is the parameter schema.
- **`personas/`** — **100,000 generated JSON personas** (JSONL, 20 shards) + `_coverage_report.json` + its own README. Start here to see the output.
- **`generator/`** — `persona_factory.py` (the v0.2 generator), `continuous-generation-operations-plan.md` (the 7-day / parallel-vs-sequential runbook), and `yt_transcript.py` (a YouTube transcript tool used for grounding real personas).
- **`research/`** — the supporting design and research documents (feasibility verdict, PersonaHub-for-India blueprint, cognitive-persona plan, realism-enhancement layer, the human-mind foundations, the build playbook, and the early creator-persona pilot).

## Status
Interim. The 100k personas are **complete and joint-consistent scaffolds** but **not yet validated predictors** — priors are approximate (pre-`ipfn`), language is structured English (pre-IndicTrans2), and the validation harness is not yet run. Each record self-reports `confidence: "interim"`. The roadmap to lift them above interim is in the spec (§11) and the operations plan.

## Quick start
```bash
# look at a persona
head -1 personas/personas_00000.jsonl | python3 -m json.tool
# generate more (≈240k/min)
python3 generator/persona_factory.py --count 1000000 --out personas --seed 2026
# or run continuously at the SLA
python3 generator/persona_factory.py --daemon --rate 100 --interval 600 --out personas
```
