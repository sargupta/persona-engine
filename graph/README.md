# Persona Knowledge Graph

A knowledge graph over the synthetic Indian personas, supporting:

- **Segmentation & analytics** — Cypher over shared dimension nodes
- **Similarity** — vector KNN over a behavioral embedding (decision-model)
- **GraphRAG** — vector retrieve → graph expand → context bundle for an LLM

## Architecture: free, no local hosting, auto-updating

The persona corpus (1M JSONL) is **not** committed to git — it's regenerated
deterministically from `generator/persona_factory.py`. So the graph is built and
hosted entirely on free GitHub infrastructure:

```
push to main (generator/ or graph/ changes)
        │
        ▼
GitHub Actions  (.github/workflows/graph-build.yml)
  1. regenerate corpus   python persona_factory.py --count 1000000 --seed 2026
  2. build Kuzu graph    python build_kuzu.py --source shards --shards all --package
  3. publish            ──►  GitHub Release  «graph-latest»
                                  persona_graph.kuzu.tar.gz   (~the whole graph, one file)
        │
        ▼
Consume anywhere, no local storage:
  Google Colab  (graph/colab_persona_graph.ipynb)
     download release → query segmentation / similarity / GraphRAG → visualize
```

| Concern | Choice | Why free |
|---|---|---|
| Engine | **Kuzu** (embedded graph DB) | no server, single-folder DB, Cypher + HNSW vector index |
| Build | **GitHub Actions** | free CI minutes; corpus regenerated with a fixed seed |
| Hosting | **GitHub Releases** | stores the graph archive free (limit 2 GB/file; ours is well under) |
| Query/Viz | **Google Colab** | free cloud compute + ephemeral disk; nothing installed locally |

Server-Neo4j was the original plan but can't be hosted free at 1M scale
(Aura Free caps ~200k nodes). The Neo4j files remain for **optional local dev**.

## Files

| File | Purpose |
|---|---|
| `build_kuzu.py` | corpus JSONL → Parquet → Kuzu COPY → vector index → `.tar.gz` |
| `query_kuzu.py` | `segment` / `similar` / `rag` against a Kuzu DB |
| `visualize.py` | schema / cohort / ego / dashboard → interactive HTML + PNG |
| `persona_fields.py` | persona JSON → flat row + 11-dim behavioral vector (shared) |
| `config.py` | paths + behavioral-embedding feature spec |
| `colab_persona_graph.ipynb` | download release + query + visualize (free, no local) |
| `../.github/workflows/graph-build.yml` | CI: regenerate → build → publish release |
| `requirements.txt` | `kuzu`, `pyarrow` |
| *(optional local Neo4j dev)* | `docker-compose.yml`, `schema.cypher`, `build_graph.py`, `query.py`, `sync.py`, `requirements-neo4j.txt` |

## Use it (zero install)

Open `graph/colab_persona_graph.ipynb` in Google Colab → Run all. It downloads
the `graph-latest` release and runs example queries. Change `REPO` if you fork.

## Build / query locally (optional)

```bash
cd graph
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# build from the 100-persona sample (fast)
.venv/bin/python build_kuzu.py --source sample --db-path persona_graph.kuzu

# or regenerate + build the full 1M (needs the generator)
python ../generator/persona_factory.py --count 1000000 --out ../personas --seed 2026
.venv/bin/python build_kuzu.py --source shards --shards all --db-path persona_graph.kuzu --package

# query
.venv/bin/python query_kuzu.py --db-path persona_graph.kuzu segment --tier manual --community OBC
.venv/bin/python query_kuzu.py --db-path persona_graph.kuzu similar --id <persona-id> --k 5
.venv/bin/python query_kuzu.py --db-path persona_graph.kuzu rag --id <persona-id> --k 3
```

## Visualize

A 1M-node graph can't be drawn whole, so `visualize.py` renders four
complementary views that together show the entire work:

| View | What it shows |
|---|---|
| **states** | personas grouped into per-state blobs (colored), linked through central occupation hubs — clustered but connected |
| **full** | the actual node+edge knowledge graph — N personas wired to every attribute hub |
| **schema** | the ontology meta-graph — every node + relationship type |
| **cohort** | a real segment of personas clustered through shared dimension hubs |
| **ego** | one persona's full neighborhood + its behavioral KNN twins |
| **dashboard** | population-scale distributions (states, jobs, values, scarcity…) |

```bash
.venv/bin/pip install -r requirements-viz.txt
.venv/bin/python visualize.py --db-path persona_graph.kuzu all   # → viz/index.html
open viz/index.html
# state-clustered graph (pretty, readable; writes states.html + states.png):
.venv/bin/python visualize.py --db-path persona_graph.kuzu states --n 3000
# the dense node+edge graph (push --n as high as the browser survives, ~3k):
.venv/bin/python visualize.py --db-path persona_graph.kuzu full --n 2000 --png
# or single views:
.venv/bin/python visualize.py --db-path persona_graph.kuzu cohort --state "Uttar Pradesh"
.venv/bin/python visualize.py --db-path persona_graph.kuzu ego --id <persona-id>
```

Interactive HTML (pyvis) opens in any browser — drag nodes, hover for detail.
The Colab notebook (cell 4) also renders a cohort subgraph inline, no install.

## Graph model

**Persona** nodes hold scalars + decision-model numerics + an `emb FLOAT[11]`
behavioral vector (min-max normalized; see `config.BEHAVIORAL_FEATURES`).
Everything categorical is a **shared dimension node**:

```
(Persona)-[:LIVES_IN]->(State)-[:IN_REGION]->(Region)
(Persona)-[:SPEAKS]->(Language)   -[:USES_DIALECT]->(Dialect)
(Persona)-[:PRACTICES]->(Religion)  -[:BELONGS_TO]->(Community)
(Persona)-[:WORKS_AS]->(Occupation)-[:HAS_TIER]->(OccupationTier)
(Persona)-[:HAS_EDUCATION]->(EducationLevel) -[:IN_CLASS]->(NccsClass) -[:HAS_INCOME_BAND]->(IncomeBand)
(Persona)-[:HOLDS_VALUE {rank, shows_up_as}]->(Value)
(Persona)-[:EXHIBITS]->(Trait)   -[:TRUSTS]->(Gatekeeper)   -[:HAS_HORIZON]->(TemporalHorizon)
```

## Auto-update

Triggered by `graph-build.yml` on push to `main` touching the generator or graph
builder. Determinism comes from the fixed `--seed` (default **2026**, the
project's canonical corpus per the root `README.md`), so the published graph is
built from the same population the validation framework checks. Run it on demand
via the Actions tab (workflow_dispatch) with custom `count` / `seed`. No secrets
required — uses the built-in `GITHUB_TOKEN`.

## Optional: local Neo4j for Browser visualization

```bash
cd graph && docker compose up -d
.venv/bin/pip install -r requirements-neo4j.txt
.venv/bin/python build_graph.py --schema --reset --source sample
# http://localhost:7474  (neo4j / personagraph)
```
