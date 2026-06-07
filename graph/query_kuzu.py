#!/usr/bin/env python3
"""Query the embedded Kuzu persona graph: segmentation, similarity, GraphRAG.

    python query_kuzu.py segment --tier manual --community OBC --state "Uttar Pradesh"
    python query_kuzu.py similar --id <persona-id> --k 5
    python query_kuzu.py rag --id <persona-id> --k 3

Point at a DB with --db-path (default ./persona_graph.kuzu). In Colab, download
the release archive, extract, and pass its path.
"""
import argparse
import json
import os

import kuzu

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "persona_graph.kuzu")


def open_conn(db_path):
    conn = kuzu.Connection(kuzu.Database(db_path))
    conn.execute("LOAD vector;")
    return conn


def _rows(res):
    cols = res.get_column_names()
    out = []
    while res.has_next():
        out.append(dict(zip(cols, res.get_next())))
    return out


# ---------------------------------------------------------------- segmentation
def segment(conn, tier=None, community=None, state=None, religion=None,
            gender=None, min_scarcity=None, limit=20):
    match = ["(p:Persona)"]
    where, params = [], {}
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
    total = _rows(conn.execute(q + " RETURN count(p) AS total", params))[0]["total"]
    sample = _rows(conn.execute(
        q + " RETURN p.id AS id, p.name AS name, p.age AS age, "
            "p.scarcity_state AS scarcity LIMIT $limit",
        {**params, "limit": limit}))
    return {"total": total, "sample": sample}


# ------------------------------------------------------------------ similarity
def _emb(conn, persona_id):
    r = _rows(conn.execute(
        "MATCH (p:Persona {id:$id}) RETURN p.emb AS emb", {"id": persona_id}))
    if not r:
        raise SystemExit(f"persona not found: {persona_id}")
    return r[0]["emb"]


def similar(conn, persona_id, k=5):
    emb = _emb(conn, persona_id)
    res = conn.execute(
        "CALL QUERY_VECTOR_INDEX('Persona','persona_behavioral', $q, $k) "
        "RETURN node.id AS id, node.name AS name, node.age AS age, "
        "node.scarcity_state AS scarcity, distance ORDER BY distance",
        {"q": emb, "k": k + 1})
    return [r for r in _rows(res) if r["id"] != persona_id][:k]


# -------------------------------------------------------------------- GraphRAG
def rag_context(conn, persona_id, k=3):
    emb = _emb(conn, persona_id)
    res = conn.execute(
        "CALL QUERY_VECTOR_INDEX('Persona','persona_behavioral', $q, $k) "
        "RETURN node.id AS id, distance ORDER BY distance",
        {"q": emb, "k": k + 1})
    neighbors = [r for r in _rows(res) if r["id"] != persona_id][:k]
    bundles = []
    for nb in neighbors:
        pid = nb["id"]
        base = _rows(conn.execute(
            "MATCH (p:Persona {id:$id})-[:LIVES_IN]->(st:State) "
            "MATCH (p)-[:WORKS_AS]->(o:Occupation)-[:HAS_TIER]->(tr:OccupationTier) "
            "RETURN p.name AS name, p.portrait AS portrait, st.name AS state, "
            "o.name AS occupation, tr.name AS tier", {"id": pid}))[0]
        values = _rows(conn.execute(
            "MATCH (p:Persona {id:$id})-[h:HOLDS_VALUE]->(v:Value) "
            "RETURN v.name AS value, h.rank AS rank, h.shows_up_as AS shows_up_as "
            "ORDER BY h.rank", {"id": pid}))
        gks = [r["g"] for r in _rows(conn.execute(
            "MATCH (p:Persona {id:$id})-[:TRUSTS]->(g:Gatekeeper) RETURN g.name AS g",
            {"id": pid}))]
        bundles.append({"id": pid, "distance": nb["distance"], **base,
                        "values": values, "gatekeepers": gks})
    return bundles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sg = sub.add_parser("segment")
    sg.add_argument("--tier"); sg.add_argument("--community")
    sg.add_argument("--state"); sg.add_argument("--religion")
    sg.add_argument("--gender"); sg.add_argument("--min-scarcity", type=float)
    sg.add_argument("--limit", type=int, default=20)

    sm = sub.add_parser("similar")
    sm.add_argument("--id", required=True); sm.add_argument("--k", type=int, default=5)

    rg = sub.add_parser("rag")
    rg.add_argument("--id", required=True); rg.add_argument("--k", type=int, default=3)

    args = ap.parse_args()
    conn = open_conn(args.db_path)
    if args.cmd == "segment":
        out = segment(conn, tier=args.tier, community=args.community,
                      state=args.state, religion=args.religion, gender=args.gender,
                      min_scarcity=args.min_scarcity, limit=args.limit)
    elif args.cmd == "similar":
        out = similar(conn, args.id, k=args.k)
    else:
        out = rag_context(conn, args.id, k=args.k)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
