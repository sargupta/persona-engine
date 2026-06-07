# Continuous Persona-Generation: 7-Day Operations Plan
### Interim run — target ≥ 100 distinct personas every 10 minutes, non-stop

**Honest framing first.** A live session cannot itself run for seven days; continuous operation runs as a **daemon on your machine/server** (script: `persona_factory.py`; launch commands in §6). This document is the runbook that daemon and its companion stages execute. The interim generator is already built, tested, and producing real records.

---

## 1. Throughput target vs. reality

| Metric | Target (SLA) | Interim generator (measured) |
|---|---|---|
| Per 10-min cycle | ≥ 100 distinct | 100 in ~0.02 s |
| Per hour | ≥ 600 | trivially met |
| Per day | ≥ 14,400 | trivially met |
| Over 7 days | ≥ 100,800 | trivially met |
| Raw ceiling (pure sampling) | — | ~3.8 × 10⁵ personas/minute, single core |

**Implication:** raw generation is *not* the bottleneck. The 10-minute cadence is therefore used as a **checkpoint/throttle** — a heartbeat that paces the expensive downstream stages (deduplication, language rendering, validation, and any LLM enrichment), not the cheap sampling step. In production the true rate limit is **enrichment + dedup at scale**, so the architecture is built around those.

---

## 2. Agent topology — what is parallel, what is sequential, and why

This is a **parallel-map → sequential-reduce** pipeline.

**PARALLEL (independent per record → scale horizontally):**
- **Generation workers** — N processes, each sharded by `state × language` so they cover different cells and rarely collide. Each writes to its own JSONL shard. (`--workers K` / one process per core, or K containers.)
- **Enrichment workers** (production) — render narrative/idiolect/utterances in the persona's L1 via IndicTrans2/LLM; parallel but **rate-limited** by API concurrency and cost cap.

**SEQUENTIAL / GLOBAL (need a whole-population view → single logical stage):**
- **Dedup service** — consumes the generation stream, drops near-duplicates. MinHash + LSH (`datasketch`) on the coordinate+psyche signature, plus cross-lingual embeddings (`sentence-transformers`/IndicBERT) for semantic dups. Can shard by LSH band but is logically one index.
- **Reweighting (ipfn)** — fits the accumulated population to real Census/NFHS/PLFS joint margins and assigns each persona a representativeness weight; runs **periodically** (every 6 h), not per record, because it needs the full set.
- **Validation gate** — hourly sampled checks; a sequential quality checkpoint.

**Rule of thumb:** anything that only looks at *one persona* is parallel; anything that needs *the whole population* (dedup index, margin fitting, distribution drift) is a sequential reduce stage.

```
[gen worker: UP/Hindi] ┐
[gen worker: TN/Tamil] ┤→ raw shards →[DEDUP]→[ENRICH]→[VALIDATE gate]→ persona store
[gen worker: WB/Bengali]┤                                   ↑
[gen worker: ...]      ┘                 [REWEIGHT ipfn every 6h]┘ + coverage-gap targeting
```

---

## 3. The repeating cycle (inside every hour)

**Every 10 minutes (×6 per hour) — the heartbeat:**
1. Parallel workers generate the batch (≥100; really thousands) → atomic shard append.
2. Dedup consumer ingests new shards, drops near-dups, updates the distinct count.
3. Checkpoint: update `_manifest.json` (total, rate, last shard, cursor) so the run is **resumable** after any crash.

**Every hour:**
- Validation sampler pulls a random sample → schema + **joint-coherence** checks (flag impossible cells, e.g. an NCCS-A2 informal labourer), **variance/tail audit** (guard against mode collapse), and **distribution drift** vs target margins (JS divergence per dimension). Append a metrics row; rotate logs.

**Every 6 hours:**
- `ipfn` reweight → refresh representativeness weights.
- Coverage-gap report → identify under-filled real cells (rare jati × region × tongue) and **bias the next workers' shard targets** to fill them (active tail-filling).

**Daily (00:00 UTC):**
- Full QA pass, snapshot/backup, dedup-index compaction, drift dashboard, disk-rotation, and a **kill-criteria** check.

---

## 4. The 7-day arc (generation never stops; the focus and grounding deepen)

| Day | Generation focus (always ≥100/10-min) | Grounding upgrade landed that day |
|---|---|---|
| 1 | Bootstrap workers + dedup + manifest; baseline priors | Stable pipeline, checkpoint/restart, observability |
| 2 | Coverage-gap targeting begins | `ipfn` reweighting to **Census/NFHS** joint margins |
| 3 | Volume scale-up across all state×language shards | **Nemotron-Personas-India** seed + **IndicTrans2** L1 rendering |
| 4 | Enrich a sampled subset (can't enrich all at rate) | Memory-stream + self-story (generative_agents / Letta) |
| 5 | Continue + start scenario sampling | **Validation harness** (`ppi_py`) + behavioural scenarios |
| 6 | Tail push — rare cells, vernacular long tail | Worker/shard expansion; variance-restoration checks |
| 7 | Consolidate | Dedup compaction, QA report, hand-off snapshot |

By Day 7 you hold a checkpointed, deduplicated, margin-fitted, partially-enriched population of well over 100k personas, with a validation harness attached and a coverage map of what is still thin.

---

## 5. Technical details to ensure (the things that break at scale)

- **Idempotency & recovery:** atomic shard writes; resume from `_manifest.json` cursor; never double-count after a crash.
- **Dedup at scale:** MinHash/LSH for surface dups + embedding similarity for semantic dups; compact the index daily.
- **Backpressure:** if enrichment lags generation, persist raw personas to disk and enrich **asynchronously** from a queue — never block the heartbeat.
- **Storage & query:** sharded JSONL for append; a **DuckDB/Parquet** index for coverage stats and drift queries; rotate shards by `--shard-size`.
- **Observability:** per-cycle counts, distinct-rate, per-dimension distribution vs target (JS/KL divergence), worker health, error/restart rates, disk headroom.
- **Reproducibility:** per-worker seeds; record the prior/version in `provenance` on every persona.
- **LLM concurrency (production):** semaphore-bounded calls, exponential-backoff retries, hard cost cap, and a fallback to non-enriched output if the budget is hit.
- **Permissions & safety:** the process writes **only** to the personas output directory; output is **synthetic** (no real individuals → DPDP-safe); names are drawn from synthetic pools and flagged.
- **Resource limits:** workers ≈ CPU cores; bound the dedup index memory; alert on disk thresholds.

---

## 6. How to run it continuously (pick one)

**A. Foreground (this/any shell), throttled to exactly the SLA:**
```
python3 persona_factory.py --daemon --rate 100 --interval 600 --out personas
```

**B. Background daemon (server), higher throughput with 4 workers:**
```
nohup python3 persona_factory.py --daemon --rate 100 --interval 600 --workers 4 \
      --out personas > gen.log 2>&1 &
```

**C. systemd service (survives reboots):**
```
# /etc/systemd/system/persona-gen.service
[Unit]
Description=Continuous synthetic-persona generation
[Service]
WorkingDirectory=/opt/personas
ExecStart=/usr/bin/python3 /opt/personas/persona_factory.py --daemon --rate 100 --interval 600 --out /data/personas
Restart=always
[Install]
WantedBy=multi-user.target
# sudo systemctl enable --now persona-gen
```

**D. cron heartbeat (one cycle every 10 min, if you prefer no long-lived process):**
```
*/10 * * * * cd /opt/personas && /usr/bin/python3 persona_factory.py --count 100 --out /data/personas >> /var/log/persona-gen.log 2>&1
```

The companion stages (dedup consumer, hourly validator, 6-hourly `ipfn` reweight, daily QA) run as their own cron/systemd timers against the same output directory — that separation is what keeps the parallel generators and the sequential reducers independent.

---

## 7. Known interim limitations (and when they close)
- **Joint inconsistencies** from semi-independent priors (e.g., class vs occupation) → closes Day 2 with `ipfn` margin fitting and joint constraints.
- **No language rendering yet** (English/structured only) → closes Day 3 with IndicTrans2.
- **No cognitive enrichment at full rate** → only a sampled subset is enriched (Day 4); the rest carry the structured schema until enriched on demand.
- **Confidence is `interim-low`** on every record until the validation harness (Day 5) and microdata grounding are in place. These personas are scaffolds, not yet validated predictors.
