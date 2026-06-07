#!/usr/bin/env python3
"""Query layer over the persona knowledge graph: segmentation, similarity,
and a GraphRAG retriever (vector search -> graph expansion -> context bundle).

CLI:
    python query.py segment --tier manual --community OBC --state "Uttar Pradesh"
    python query.py similar --id <persona-id> --k 5
    python query.py rag --id <persona-id> --k 3
"""
import argparse
import json

from neo4j import GraphDatabase

import config


def connect():
    return GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))


# ---------------------------------------------------------------- segmentation
def segment(driver, tier=None, community=None, state=None, religion=None,
            min_scarcity=None, gender=None, limit=20):
    where, params = [], {"limit": limit}
    match = ["(p:Persona)"]
    if tier:
        match.append("(p)-[:WORKS_AS]->(:Occupation)-[:HAS_TIER]->(:OccupationTier {name:$tier})")
        params["tier"] = tier
    if community:
        match.append("(p)-[:BELONGS_TO]->(:Community {name:$community})")
        params["community"] = community
    if state:
        match.append("(p)-[:LIVES_IN]->(:State {name:$state})")
        params["state"] = state
    if religion:
        match.append("(p)-[:PRACTICES]->(:Religion {name:$religion})")
        params["religion"] = religion
    if gender:
        where.append("p.gender = $gender")
        params["gender"] = gender
    if min_scarcity is not None:
        where.append("p.scarcity_state >= $min_scarcity")
        params["min_scarcity"] = min_scarcity
    q = "MATCH " + ", ".join(match)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += (" RETURN count(p) AS total, "
          "collect({id:p.id, name:p.name, age:p.age, scarcity:p.scarcity_state})[0..$limit] AS sample")
    with driver.session(database=config.NEO4J_DATABASE) as s:
        rec = s.run(q, **params).single()
        return {"total": rec["total"], "sample": rec["sample"]}


# ------------------------------------------------------------------ similarity
def similar(driver, persona_id, k=5):
    q = """
    MATCH (src:Persona {id:$id})
    CALL db.index.vector.queryNodes('persona_behavioral', $k1, src.embedding_behavioral)
    YIELD node, score
    WHERE node.id <> $id
    RETURN node.id AS id, node.name AS name, node.age AS age,
           node.scarcity_state AS scarcity, score
    ORDER BY score DESC LIMIT $k
    """
    with driver.session(database=config.NEO4J_DATABASE) as s:
        return [dict(r) for r in s.run(q, id=persona_id, k1=k + 1, k=k)]


# -------------------------------------------------------------------- GraphRAG
def rag_context(driver, persona_id, k=3):
    """Vector-retrieve k nearest personas, then 1-hop expand each into a
    grounded context bundle (identity, values, trust network) for an LLM."""
    q = """
    MATCH (src:Persona {id:$id})
    CALL db.index.vector.queryNodes('persona_behavioral', $k1, src.embedding_behavioral)
    YIELD node, score
    WITH node, score WHERE node.id <> $id
    WITH node, score ORDER BY score DESC LIMIT $k
    MATCH (node)-[:LIVES_IN]->(st:State)
    MATCH (node)-[:WORKS_AS]->(occ:Occupation)-[:HAS_TIER]->(tier:OccupationTier)
    OPTIONAL MATCH (node)-[hv:HOLDS_VALUE]->(v:Value)
    OPTIONAL MATCH (node)-[:TRUSTS]->(gk:Gatekeeper)
    RETURN node.id AS id, node.name AS name, node.portrait AS portrait,
           score, st.name AS state, occ.name AS occupation, tier.name AS tier,
           collect(DISTINCT {value:v.name, rank:hv.rank, shows_up_as:hv.shows_up_as}) AS values,
           collect(DISTINCT gk.name) AS gatekeepers
    """
    with driver.session(database=config.NEO4J_DATABASE) as s:
        return [dict(r) for r in s.run(q, id=persona_id, k1=k + 1, k=k)]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sg = sub.add_parser("segment")
    sg.add_argument("--tier")
    sg.add_argument("--community")
    sg.add_argument("--state")
    sg.add_argument("--religion")
    sg.add_argument("--gender")
    sg.add_argument("--min-scarcity", type=float)
    sg.add_argument("--limit", type=int, default=20)

    sm = sub.add_parser("similar")
    sm.add_argument("--id", required=True)
    sm.add_argument("--k", type=int, default=5)

    rg = sub.add_parser("rag")
    rg.add_argument("--id", required=True)
    rg.add_argument("--k", type=int, default=3)

    args = ap.parse_args()
    driver = connect()
    try:
        if args.cmd == "segment":
            out = segment(driver, tier=args.tier, community=args.community,
                          state=args.state, religion=args.religion,
                          gender=args.gender, min_scarcity=args.min_scarcity,
                          limit=args.limit)
        elif args.cmd == "similar":
            out = similar(driver, args.id, k=args.k)
        else:
            out = rag_context(driver, args.id, k=args.k)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
