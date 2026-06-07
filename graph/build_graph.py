#!/usr/bin/env python3
"""Build / update the persona knowledge graph in Neo4j.

Idempotent: re-running on the same data is a no-op (everything MERGEd on
stable keys). Used both for initial bulk load and for incremental sync.

Examples:
    python build_graph.py --schema --source sample          # phase 0
    python build_graph.py --source shards --shards 0-9       # 10 shards
    python build_graph.py --source shards --shards all       # full 1M
    python build_graph.py --reset                            # wipe graph
"""
import argparse
import glob
import os
import sys
import time

from neo4j import GraphDatabase

import config
from persona_fields import iter_rows

INGEST_CYPHER = """
UNWIND $rows AS row
MERGE (p:Persona {id: row.id})
SET p.name = row.name,
    p.age = row.age,
    p.gender = row.gender,
    p.setting = row.setting,
    p.portrait = row.portrait,
    p.capital_index = row.capital_index,
    p.loss_aversion_lambda = row.loss_aversion_lambda,
    p.present_bias_beta = row.present_bias_beta,
    p.scarcity_state = row.scarcity_state,
    p.reflective_disposition = row.reflective_disposition,
    p.novelty_resistance_index = row.novelty_resistance_index,
    p.peak_exhaustion_hour = row.peak_exhaustion_hour,
    p.inflation_elasticity = row.inflation_elasticity,
    p.embedding_behavioral = row.embedding_behavioral
WITH p, row
MERGE (st:State {name: row.state})
MERGE (rg:Region {name: row.region})
MERGE (st)-[:IN_REGION]->(rg)
MERGE (p)-[:LIVES_IN]->(st)
MERGE (lang:Language {name: row.language})
MERGE (p)-[:SPEAKS]->(lang)
MERGE (relig:Religion {name: row.religion})
MERGE (p)-[:PRACTICES]->(relig)
MERGE (com:Community {name: row.community})
MERGE (p)-[:BELONGS_TO]->(com)
MERGE (occ:Occupation {name: row.occupation})
MERGE (tier:OccupationTier {name: row.occupation_tier})
MERGE (occ)-[:HAS_TIER]->(tier)
MERGE (p)-[:WORKS_AS]->(occ)
MERGE (edu:EducationLevel {name: row.education})
MERGE (p)-[:HAS_EDUCATION]->(edu)
MERGE (nc:NccsClass {name: row.class_nccs})
MERGE (p)-[:IN_CLASS]->(nc)
MERGE (ib:IncomeBand {name: row.income_band})
MERGE (p)-[:HAS_INCOME_BAND]->(ib)
MERGE (th:TemporalHorizon {name: row.temporal_horizon})
MERGE (p)-[:HAS_HORIZON]->(th)
FOREACH (_ IN CASE WHEN row.dialect IS NULL THEN [] ELSE [1] END |
  MERGE (d:Dialect {name: row.dialect})
  MERGE (p)-[:USES_DIALECT]->(d))
FOREACH (t IN row.traits |
  MERGE (tr:Trait {name: t})
  MERGE (p)-[:EXHIBITS]->(tr))
FOREACH (g IN row.gatekeepers |
  MERGE (gk:Gatekeeper {name: g})
  MERGE (p)-[:TRUSTS]->(gk))
WITH p, row
UNWIND (CASE WHEN size(row.values) = 0 THEN [null] ELSE row.values END) AS cv
FOREACH (_ IN CASE WHEN cv IS NULL THEN [] ELSE [1] END |
  MERGE (v:Value {name: cv.value})
  MERGE (p)-[hv:HOLDS_VALUE]->(v)
  SET hv.rank = cv.rank, hv.shows_up_as = cv.shows_up_as)
"""


def connect():
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
    )


def apply_schema(driver):
    with open(os.path.join(os.path.dirname(__file__), "schema.cypher")) as fh:
        body = fh.read()
    applied = 0
    with driver.session(database=config.NEO4J_DATABASE) as session:
        for chunk in body.split(";"):
            # drop comment lines first, then check if anything remains
            clean = "\n".join(
                l for l in chunk.splitlines() if not l.strip().startswith("//")).strip()
            if clean:
                session.run(clean).consume()
                applied += 1
    print(f"schema applied ({applied} statements)")


def reset(driver):
    with driver.session(database=config.NEO4J_DATABASE) as session:
        session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS")
    print("graph wiped")


def load_files(driver, paths, limit=None, batch_size=1000):
    total, t0 = 0, time.time()
    batch = []
    with driver.session(database=config.NEO4J_DATABASE) as session:
        for row in iter_rows(paths, limit=limit):
            batch.append(row)
            if len(batch) >= batch_size:
                session.run(INGEST_CYPHER, rows=batch)
                total += len(batch)
                batch = []
                if total % 10000 == 0:
                    rate = total / max(1e-6, time.time() - t0)
                    print(f"  ingested {total:,}  ({rate:,.0f}/s)")
        if batch:
            session.run(INGEST_CYPHER, rows=batch)
            total += len(batch)
    print(f"ingested {total:,} personas in {time.time()-t0:,.1f}s")
    return total


def resolve_paths(args):
    if args.source == "sample":
        return [os.path.join(config.PERSONAS_DIR, "sample_personas.jsonl")]
    all_shards = sorted(glob.glob(os.path.join(config.PERSONAS_DIR, "personas_*.jsonl")))
    if args.shards in (None, "all"):
        return all_shards
    lo, _, hi = args.shards.partition("-")
    lo = int(lo)
    hi = int(hi) if hi else lo
    return [p for p in all_shards
            if lo <= int(os.path.basename(p)[9:14]) <= hi]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", action="store_true", help="apply constraints + vector index")
    ap.add_argument("--reset", action="store_true", help="wipe all nodes first")
    ap.add_argument("--source", choices=["sample", "shards"], default="sample")
    ap.add_argument("--shards", help="e.g. '0', '0-9', or 'all'")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=1000)
    args = ap.parse_args()

    driver = connect()
    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"cannot reach Neo4j at {config.NEO4J_URI}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.reset:
        reset(driver)
    if args.schema:
        apply_schema(driver)
    paths = resolve_paths(args)
    print(f"loading {len(paths)} file(s)")
    load_files(driver, paths, limit=args.limit, batch_size=args.batch_size)
    driver.close()


if __name__ == "__main__":
    main()
