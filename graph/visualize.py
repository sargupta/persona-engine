#!/usr/bin/env python3
"""Visualize the Kuzu persona graph.

A 1M-node graph can't be drawn whole, so this renders four complementary views
that together *show the entire work*:

  schema     the ontology meta-graph (node + relationship types)        -> HTML
  cohort     a segment of personas linked through shared dimension hubs -> HTML
  ego        one persona's full neighborhood + behavioral KNN neighbors -> HTML
  dashboard  population-scale distributions (states, jobs, values, ...) -> PNG

All views open in a browser; the dashboard is a static image. An index.html
links them so the whole thing is one click.

    python visualize.py --db-path persona_viz.kuzu all
    python visualize.py --db-path persona_viz.kuzu cohort --state "Uttar Pradesh"
    python visualize.py --db-path persona_viz.kuzu ego --id <persona-id>

Deps: pyvis, networkx, matplotlib (see requirements-viz.txt).
"""
import argparse
import os
from collections import Counter

import kuzu

OUT = os.path.join(os.path.dirname(__file__), "viz")

# label -> (hex color, node size) for a consistent legend across views
PALETTE = {
    "Persona": ("#5b8def", 14),
    "State": ("#2a9d8f", 22), "Region": ("#1d7268", 26),
    "Language": ("#e9c46a", 20), "Dialect": ("#d4a72c", 18),
    "Religion": ("#e76f51", 22), "Community": ("#c1492e", 20),
    "Occupation": ("#9b5de5", 22), "OccupationTier": ("#7b3fc4", 26),
    "EducationLevel": ("#f4a261", 20), "NccsClass": ("#e08c3c", 20),
    "IncomeBand": ("#cf7723", 20), "Value": ("#f15bb5", 18),
    "Trait": ("#00bbf9", 16), "Gatekeeper": ("#00f5d4", 18),
    "TemporalHorizon": ("#43aa8b", 20),
}
# Persona -> dimension edges  (rel label, target label)
P_EDGES = [
    ("LIVES_IN", "State"), ("SPEAKS", "Language"), ("PRACTICES", "Religion"),
    ("BELONGS_TO", "Community"), ("WORKS_AS", "Occupation"),
    ("HAS_EDUCATION", "EducationLevel"), ("IN_CLASS", "NccsClass"),
    ("HAS_INCOME_BAND", "IncomeBand"), ("HAS_HORIZON", "TemporalHorizon"),
    ("USES_DIALECT", "Dialect"), ("EXHIBITS", "Trait"),
    ("TRUSTS", "Gatekeeper"), ("HOLDS_VALUE", "Value"),
]
DIM_EDGES = [("IN_REGION", "State", "Region"),
             ("HAS_TIER", "Occupation", "OccupationTier")]


def conn(db_path):
    c = kuzu.Connection(kuzu.Database(db_path))
    c.execute("LOAD vector;")
    return c


def rows(res):
    cols = res.get_column_names()
    out = []
    while res.has_next():
        out.append(dict(zip(cols, res.get_next())))
    return out


def _net(height="780px"):
    from pyvis.network import Network
    n = Network(height=height, width="100%", bgcolor="#0e1117",
                font_color="#e6e6e6", cdn_resources="in_line", directed=True)
    n.barnes_hut(gravity=-12000, spring_length=110, spring_strength=0.015)
    n.toggle_physics(True)
    return n


def _save(net, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    net.write_html(path, notebook=False, open_browser=False)
    print("wrote", path)
    return path


# --------------------------------------------------------------------- schema
def view_schema():
    """The ontology: every node type and how they connect. The 'map' of the work."""
    net = _net("680px")
    for label, (color, size) in PALETTE.items():
        net.add_node(label, label=label, color=color, size=size + 8,
                     shape="dot", title=f"{label} node type")
    for rel, tgt in P_EDGES:
        net.add_edge("Persona", tgt, label=rel, color="#3a4a63",
                     font={"size": 9, "color": "#9aa7bd"})
    for rel, src, tgt in DIM_EDGES:
        net.add_edge(src, tgt, label=rel, color="#55607a",
                     font={"size": 9, "color": "#9aa7bd"})
    return _save(net, "schema.html")


# --------------------------------------------------------------------- cohort
def view_cohort(c, state=None, community=None, tier=None, limit=40):
    """A segment of real personas clustered through the dimension hubs they share."""
    match = ["(p:Persona)"]
    where, params = [], {}
    if state:
        match.append("(p)-[:LIVES_IN]->(:State {name:$state})"); params["state"] = state
    if community:
        match.append("(p)-[:BELONGS_TO]->(:Community {name:$community})"); params["community"] = community
    if tier:
        match.append("(p)-[:WORKS_AS]->(:Occupation)-[:HAS_TIER]->(:OccupationTier {name:$tier})")
        params["tier"] = tier
    q = "MATCH " + ", ".join(match) + " RETURN p.id AS id LIMIT $limit"
    ids = [r["id"] for r in rows(c.execute(q, {**params, "limit": limit}))]
    if not ids:
        raise SystemExit("empty cohort — loosen the filters")

    net = _net()
    seen = set()
    for pid in ids:
        det = rows(c.execute(
            "MATCH (p:Persona {id:$id}) OPTIONAL MATCH (p)-[:LIVES_IN]->(s:State) "
            "OPTIONAL MATCH (p)-[:WORKS_AS]->(o:Occupation) "
            "OPTIONAL MATCH (p)-[:PRACTICES]->(r:Religion) "
            "RETURN p.name AS name, p.scarcity_state AS sc, s.name AS state, "
            "o.name AS occ, r.name AS rel", {"id": pid}))[0]
        c_, sz = PALETTE["Persona"]
        net.add_node(pid, label=det["name"], color=c_, size=sz,
                     title=f"{det['name']} · scarcity {det['sc']:.2f}")
        for label, key in (("State", "state"), ("Occupation", "occ"), ("Religion", "rel")):
            val = det[key]
            if not val:
                continue
            nid = f"{label}:{val}"
            if nid not in seen:
                col, s = PALETTE[label]
                net.add_node(nid, label=val, color=col, size=s, shape="dot")
                seen.add(nid)
            net.add_edge(pid, nid, color="#33405a")
        # top value
        v = rows(c.execute(
            "MATCH (p:Persona {id:$id})-[h:HOLDS_VALUE]->(vl:Value) "
            "RETURN vl.name AS v ORDER BY h.rank LIMIT 1", {"id": pid}))
        if v:
            nid = f"Value:{v[0]['v']}"
            if nid not in seen:
                col, s = PALETTE["Value"]
                net.add_node(nid, label=v[0]["v"], color=col, size=s, shape="diamond")
                seen.add(nid)
            net.add_edge(pid, nid, color="#5a335a")
    tag = state or community or tier or "all"
    return _save(net, f"cohort_{tag}.html".replace(" ", "_"))


# ------------------------------------------------------------------------ ego
def view_ego(c, persona_id=None, k=6):
    """One persona, its full attribute neighborhood, and behavioral KNN twins."""
    if not persona_id:
        persona_id = rows(c.execute("MATCH (p:Persona) RETURN p.id AS id LIMIT 1"))[0]["id"]
    base = rows(c.execute("MATCH (p:Persona {id:$id}) RETURN p.name AS name, "
                          "p.emb AS emb, p.scarcity_state AS sc", {"id": persona_id}))
    if not base:
        raise SystemExit(f"persona not found: {persona_id}")
    name, emb = base[0]["name"], base[0]["emb"]
    net = _net()
    col, sz = PALETTE["Persona"]
    net.add_node(persona_id, label=name, color="#ffd166", size=30,
                 title=f"{name} (focus)", shape="star")

    for rel, tgt in P_EDGES:
        for r in rows(c.execute(
                f"MATCH (p:Persona {{id:$id}})-[:{rel}]->(d:{tgt}) "
                f"RETURN d.name AS n", {"id": persona_id})):
            if r["n"] is None:
                continue
            nid = f"{tgt}:{r['n']}"
            color, s = PALETTE[tgt]
            net.add_node(nid, label=r["n"], color=color, size=s)
            net.add_edge(persona_id, nid, label=rel, color="#33405a",
                         font={"size": 8, "color": "#7a87a0"})
    # behavioral twins
    twins = [t for t in rows(c.execute(
        "CALL QUERY_VECTOR_INDEX('Persona','persona_behavioral', $q, $k) "
        "RETURN node.id AS id, node.name AS name, distance ORDER BY distance",
        {"q": emb, "k": k + 1})) if t["id"] != persona_id][:k]
    for t in twins:
        net.add_node(t["id"], label=t["name"], color=col, size=sz,
                     title=f"{t['name']} · dist {t['distance']:.3f}")
        net.add_edge(persona_id, t["id"], label="~similar", color="#2a9d8f",
                     dashes=True, font={"size": 8, "color": "#2a9d8f"})
    return _save(net, f"ego_{persona_id[:8]}.html")


# ------------------------------------------------------------------ dashboard
def view_dashboard(c, top=12):
    """Population-scale distributions — the whole corpus as charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def dist(rel, tgt, n=top):
        r = rows(c.execute(
            f"MATCH (:Persona)-[:{rel}]->(d:{tgt}) RETURN d.name AS k, "
            f"count(*) AS c ORDER BY c DESC LIMIT {n}"))
        return [x["k"] for x in r], [x["c"] for x in r]

    total = rows(c.execute("MATCH (p:Persona) RETURN count(p) AS c"))[0]["c"]
    panels = [
        ("Top states (LIVES_IN)", *dist("LIVES_IN", "State")),
        ("Occupations (WORKS_AS)", *dist("WORKS_AS", "Occupation")),
        ("Religions (PRACTICES)", *dist("PRACTICES", "Religion", 8)),
        ("Top values (HOLDS_VALUE)", *dist("HOLDS_VALUE", "Value")),
        ("Education (HAS_EDUCATION)", *dist("HAS_EDUCATION", "EducationLevel", 8)),
        ("Income band (HAS_INCOME_BAND)", *dist("HAS_INCOME_BAND", "IncomeBand", 8)),
    ]
    sc = [r["s"] for r in rows(c.execute(
        "MATCH (p:Persona) RETURN p.scarcity_state AS s"))]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(3, 3, figsize=(20, 13))
    fig.suptitle(f"Persona graph — {total:,} personas", fontsize=18, color="#ffd166")
    flat = axes.flatten()
    colors = ["#5b8def", "#9b5de5", "#e76f51", "#f15bb5", "#f4a261", "#2a9d8f"]
    for ax, (title, labels, vals), col in zip(flat, panels, colors):
        ax.barh(range(len(labels)), vals, color=col)
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis(); ax.set_title(title, fontsize=12, color="#e6e6e6")
        ax.tick_params(colors="#9aa7bd")
    # scarcity histogram
    ax = flat[6]; ax.hist(sc, bins=30, color="#00bbf9")
    ax.set_title("Scarcity state distribution", fontsize=12)
    ax.tick_params(colors="#9aa7bd")
    # gender split
    g = rows(c.execute("MATCH (p:Persona) RETURN p.gender AS g, count(*) AS c ORDER BY c DESC"))
    flat[7].pie([x["c"] for x in g], labels=[x["g"] for x in g], autopct="%1.0f%%",
                colors=["#5b8def", "#f15bb5", "#f4a261", "#2a9d8f"])
    flat[7].set_title("Gender split", fontsize=12)
    # node-type counts
    ax = flat[8]
    tbls = ["State", "Occupation", "Value", "Religion", "Community", "Language"]
    cnts = [rows(c.execute(f"MATCH (n:{t}) RETURN count(n) AS c"))[0]["c"] for t in tbls]
    ax.bar(tbls, cnts, color="#43aa8b")
    ax.set_title("Distinct dimension nodes", fontsize=12)
    ax.tick_params(axis="x", rotation=45, colors="#9aa7bd")
    ax.tick_params(axis="y", colors="#9aa7bd")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "dashboard.png")
    fig.savefig(path, dpi=110, facecolor="#0e1117")
    print("wrote", path)
    return path


# ----------------------------------------------------------------------- index
def write_index(items):
    os.makedirs(OUT, exist_ok=True)
    cards = "\n".join(
        f'<a class="card" href="{os.path.basename(p)}">'
        f'<h3>{t}</h3><p>{d}</p></a>' for t, d, p in items)
    html = f"""<!doctype html><meta charset=utf-8>
<title>Persona graph — visualizations</title>
<style>
 body{{background:#0e1117;color:#e6e6e6;font:15px/1.5 system-ui;margin:0;padding:40px}}
 h1{{color:#ffd166}} .grid{{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));margin-top:24px}}
 .card{{display:block;padding:22px;background:#161b22;border:1px solid #283041;border-radius:12px;color:inherit;text-decoration:none;transition:.15s}}
 .card:hover{{border-color:#5b8def;transform:translateY(-2px)}}
 .card h3{{margin:0 0 6px;color:#5b8def}} .card p{{margin:0;color:#9aa7bd;font-size:13px}}
 img{{max-width:100%;border-radius:12px;margin-top:8px}}
</style>
<h1>Persona Knowledge Graph — visualizations</h1>
<p style=color:#9aa7bd>Interactive views of the Kuzu graph. Click a card.</p>
<div class=grid>{cards}</div>
"""
    path = os.path.join(OUT, "index.html")
    with open(path, "w") as f:
        f.write(html)
    print("wrote", path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=os.path.join(os.path.dirname(__file__), "persona_graph.kuzu"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema")
    co = sub.add_parser("cohort")
    co.add_argument("--state"); co.add_argument("--community")
    co.add_argument("--tier"); co.add_argument("--limit", type=int, default=40)
    eg = sub.add_parser("ego"); eg.add_argument("--id"); eg.add_argument("--k", type=int, default=6)
    sub.add_parser("dashboard")
    al = sub.add_parser("all"); al.add_argument("--state", default="Uttar Pradesh")
    args = ap.parse_args()
    c = conn(args.db_path)

    if args.cmd == "schema":
        view_schema()
    elif args.cmd == "cohort":
        view_cohort(c, args.state, args.community, args.tier, args.limit)
    elif args.cmd == "ego":
        view_ego(c, args.id)
    elif args.cmd == "dashboard":
        view_dashboard(c)
    elif args.cmd == "all":
        sp = view_schema()
        dp = view_dashboard(c)
        cp = view_cohort(c, state=args.state)
        pid = rows(c.execute("MATCH (p:Persona) RETURN p.id AS id LIMIT 1"))[0]["id"]
        ep = view_ego(c, pid)
        idx = write_index([
            ("Schema / ontology", "Every node + relationship type — the map of the graph", sp),
            ("Population dashboard", "Distributions across the whole corpus", dp),
            (f"Cohort: {args.state}", "Real personas clustered through shared hubs", cp),
            ("Ego network", "One persona's neighborhood + behavioral twins", ep),
        ])
        print("\nopen:", idx)


if __name__ == "__main__":
    main()
