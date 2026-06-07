#!/usr/bin/env python3
"""Persona-to-persona INTERACTION layer + emergent communities.

The base graph is bipartite (Persona -> shared attribute hubs); personas never
link to each other. This builds the missing layer: a weighted "who would
plausibly communicate" network, then lets communities *emerge* (Louvain) rather
than imposing administrative buckets like state.

Edge weight = composite homophily / communication-feasibility:
    behavioral similarity  (decision-model embedding, cosine)
  + shared trust anchor    (same institutional gatekeeper  -> a real social tie)
  + co-location            (same state / same region)
  + shared channel         (same language)
  + social stratum         (same community)

Candidate pairs are generated sparsely (behavioral KNN + same state+community
peers) so this scales — never all-pairs. Output:
    viz/interactions.png      community-colored force layout (static)
    viz/interactions.html     interactive (pyvis)
    viz/communities.json      per-community profile + key connectors
Optionally materialize edges back into Kuzu as INTERACTS_WITH (--write-db).

    python interactions.py --db-path persona_viz.kuzu --n 4000
"""
import argparse
import json
import os
import random
from collections import Counter, defaultdict

import kuzu
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "viz")

# affinity weights (sum = 1.0)
W = dict(behavioral=0.34, gatekeeper=0.22, state=0.16, region=0.06,
         language=0.12, community=0.10)
EDGE_THRESHOLD = 0.42   # keep a candidate pair as an edge above this


def rows(res):
    cols = res.get_column_names()
    out = []
    while res.has_next():
        out.append(dict(zip(cols, res.get_next())))
    return out


def load(c, n):
    """Pull a sample of personas with every interaction-relevant attribute."""
    core = rows(c.execute(
        "MATCH (p:Persona)-[:LIVES_IN]->(s:State) "
        "OPTIONAL MATCH (s)-[:IN_REGION]->(rg:Region) "
        "OPTIONAL MATCH (p)-[:SPEAKS]->(l:Language) "
        "OPTIONAL MATCH (p)-[:PRACTICES]->(rel:Religion) "
        "OPTIONAL MATCH (p)-[:BELONGS_TO]->(cm:Community) "
        "OPTIONAL MATCH (p)-[:WORKS_AS]->(o:Occupation) "
        "RETURN p.id AS id, p.name AS name, p.emb AS emb, p.scarcity_state AS sc, "
        "s.name AS state, rg.name AS region, l.name AS language, "
        "rel.name AS religion, cm.name AS community, o.name AS occupation "
        "LIMIT $n", {"n": n}))
    ids = [r["id"] for r in core]
    idset = set(ids)

    def multimap(rel, tgt):
        m = defaultdict(list)
        for r in rows(c.execute(
                f"MATCH (p:Persona)-[:{rel}]->(d:{tgt}) WHERE p.id IN $ids "
                f"RETURN p.id AS id, d.name AS n", {"ids": ids})):
            if r["id"] in idset:
                m[r["id"]].append(r["n"])
        return m

    gk = multimap("TRUSTS", "Gatekeeper")
    vals = defaultdict(list)
    for r in rows(c.execute(
            "MATCH (p:Persona)-[h:HOLDS_VALUE]->(v:Value) WHERE p.id IN $ids "
            "RETURN p.id AS id, v.name AS v ORDER BY h.rank", {"ids": ids})):
        if r["id"] in idset:
            vals[r["id"]].append(r["v"])
    traits = multimap("EXHIBITS", "Trait")
    return core, gk, vals, traits


def candidate_pairs(core, emb, knn=10, peers=5):
    """Sparse candidate set: behavioral KNN (global) + same state+community peers."""
    n = len(core)
    # cosine similarity matrix on the embedding (small N — fine in numpy)
    norm = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    cand = set()
    # behavioral KNN
    B = 512
    for s in range(0, n, B):
        sim = norm[s:s + B] @ norm.T            # (B, n)
        for i_local, i in enumerate(range(s, min(s + B, n))):
            row = sim[i_local]
            top = np.argpartition(-row, knn + 1)[:knn + 1]
            for j in top:
                j = int(j)
                if j != i:
                    cand.add((min(i, j), max(i, j)))
    # same state+community social peers
    buckets = defaultdict(list)
    for i, r in enumerate(core):
        buckets[(r["state"], r["community"])].append(i)
    rnd = random.Random(11)
    for members in buckets.values():
        if len(members) < 2:
            continue
        for i in members:
            for j in rnd.sample(members, min(peers, len(members))):
                if i != j:
                    cand.add((min(i, j), max(i, j)))
    return cand, norm


def score(core, gk, norm, cand):
    """Score each candidate pair; return edges (i, j, weight) above threshold."""
    edges = []
    for i, j in cand:
        a, b = core[i], core[j]
        beh = float(norm[i] @ norm[j])                 # cosine in [-1,1]
        beh = max(0.0, beh)
        shared_gk = bool(set(gk.get(a["id"], [])) & set(gk.get(b["id"], [])))
        w = (W["behavioral"] * beh
             + W["gatekeeper"] * (1.0 if shared_gk else 0.0)
             + W["state"] * (a["state"] == b["state"])
             + W["region"] * (a["region"] == b["region"] and a["region"] is not None)
             + W["language"] * (a["language"] == b["language"] and a["language"] is not None)
             + W["community"] * (a["community"] == b["community"] and a["community"] is not None))
        if w >= EDGE_THRESHOLD:
            edges.append((i, j, round(w, 4)))
    return edges


def detect(core, edges):
    import networkx as nx
    from networkx.algorithms.community import louvain_communities
    G = nx.Graph()
    G.add_nodes_from(range(len(core)))
    for i, j, w in edges:
        G.add_edge(i, j, weight=w)
    comms = louvain_communities(G, weight="weight", seed=7, resolution=1.0)
    comms = sorted(comms, key=len, reverse=True)
    cid = {}
    for k, members in enumerate(comms):
        for m in members:
            cid[m] = k
    return G, comms, cid


def profile(core, vals, traits, comms, G, top=12):
    """Describe each community: dominant attributes + most-connected member."""
    deg = dict(G.degree())
    out = []
    for k, members in enumerate(comms[:top]):
        if len(members) < 3:
            continue
        def topc(key, src=core, n=3):
            cnt = Counter()
            for m in members:
                v = src[m].get(key) if isinstance(src[m], dict) else None
                if v:
                    cnt[v] += 1
            return cnt.most_common(n)
        vc, tc = Counter(), Counter()
        for m in members:
            vc.update(vals.get(core[m]["id"], []))
            tc.update(traits.get(core[m]["id"], []))
        hub = max(members, key=lambda m: deg.get(m, 0))
        out.append({
            "community": k, "size": len(members),
            "top_states": topc("state"), "top_occupations": topc("occupation"),
            "top_communities": topc("community"), "top_religions": topc("religion"),
            "top_values": vc.most_common(4), "top_traits": tc.most_common(3),
            "key_connector": {"name": core[hub]["name"], "state": core[hub]["state"],
                              "occupation": core[hub]["occupation"], "degree": deg.get(hub, 0)},
        })
    return out


def _palette(k):
    import colorsys
    return [f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            for r, g, b in (colorsys.hsv_to_rgb((i * 0.61803) % 1.0, 0.66, 0.97)
                            for i in range(k))]


def clustered_layout(comms, cid, G):
    """Group-in-a-box: community centroids laid out by inter-community ties
    (connected communities sit near each other), nodes spring-placed within
    their community blob. Gives clustered-but-connected, not a uniform cloud."""
    import networkx as nx
    big = [k for k, m in enumerate(comms) if len(m) >= 3]
    # meta-graph of communities weighted by edges between them
    meta = nx.Graph()
    meta.add_nodes_from(big)
    cross = Counter()
    for i, j in G.edges():
        ci, cj = cid.get(i), cid.get(j)
        if ci != cj and ci in big and cj in big:
            cross[(min(ci, cj), max(ci, cj))] += 1
    for (a, b), w in cross.items():
        meta.add_edge(a, b, weight=w)
    centers = nx.spring_layout(meta, weight="weight", k=2.2, iterations=250, seed=5)
    # scale community footprint by sqrt(size) but keep blobs well inside the gaps
    pos = {}
    SPREAD = 18.0
    for k in big:
        members = [m for m in comms[k] if G.degree(m) > 0]
        if not members:
            continue
        sub = G.subgraph(members)
        local = nx.spring_layout(sub, weight="weight", k=0.6, iterations=40, seed=k)
        rad = 0.6 + 0.16 * np.sqrt(len(members))
        cx, cy = centers.get(k, (0, 0))
        for m, (lx, ly) in local.items():
            pos[m] = (cx * SPREAD + lx * rad, cy * SPREAD + ly * rad)
    return pos, big


def render(core, comms, cid, G, pos, big, palette):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    H = G.subgraph(list(pos))
    deg = dict(H.degree())

    plt.figure(figsize=(24, 24), facecolor="#0e1117")
    ax = plt.gca(); ax.set_facecolor("#0e1117")
    # intra-community edges in community color (faint); inter-community edges grey
    intra = [(i, j) for i, j in H.edges() if cid.get(i) == cid.get(j)]
    inter = [(i, j) for i, j in H.edges() if cid.get(i) != cid.get(j)]
    nx.draw_networkx_edges(H, pos, edgelist=inter, alpha=0.04,
                           edge_color="#6b78aa", width=0.25)
    nx.draw_networkx_edges(H, pos, edgelist=intra, alpha=0.10, width=0.3,
                           edge_color=[palette[cid[i]] for i, _ in intra])
    nx.draw_networkx_nodes(H, pos, nodelist=list(H),
                           node_size=[14 + 6 * deg[n] for n in H],
                           node_color=[palette[cid.get(n, 0)] for n in H], linewidths=0)
    # label the larger communities, above their blob
    sized = sorted(big, key=lambda k: -len(comms[k]))[:14]
    for k in sized:
        mm = [m for m in comms[k] if m in pos]
        if not mm:
            continue
        cx = np.mean([pos[m][0] for m in mm]); cy = max(pos[m][1] for m in mm)
        st = Counter(core[m]["state"] for m in mm).most_common(1)[0][0]
        oc = Counter(core[m]["occupation"] for m in mm if core[m]["occupation"]).most_common(1)
        lbl = f"#{k} {st}" + (f"\n{oc[0][0]}" if oc else "")
        ax.text(cx, cy + 0.4, lbl, fontsize=10, color="#fff", ha="center", va="bottom",
                fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.3", fc=palette[k], ec="none", alpha=0.7))
    ax.axis("off"); plt.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "interactions.png")
    plt.savefig(path, dpi=80, facecolor="#0e1117"); plt.close()
    print("wrote", path, f"({H.number_of_nodes()} nodes, {H.number_of_edges()} edges)")
    return path, palette


def render_html(core, edges, cid, palette, G, pos):
    from pyvis.network import Network
    H = G.subgraph(list(pos))
    deg = dict(H.degree())
    net = Network(height="900px", width="100%", bgcolor="#0e1117",
                  font_color="#e6e6e6", cdn_resources="in_line")
    net.set_options('{"nodes":{"shape":"dot","borderWidth":0},'
                    '"edges":{"smooth":false,"color":{"opacity":0.10}},'
                    '"physics":{"enabled":false},'
                    '"interaction":{"hideEdgesOnDrag":true,"dragNodes":true,'
                    '"tooltipDelay":80}}')
    SC = 60   # scale layout coords to pixels
    for n in H:
        r = core[n]
        x, y = pos[n]
        net.add_node(n, label=" ", x=x * SC, y=y * SC, size=6 + 1.5 * deg[n],
                     color=palette[cid.get(n, 0)],
                     title=f"{r['name']} · {r['state']} · {r['occupation']} "
                           f"· community #{cid.get(n,0)}")
    for i, j, w in edges:
        if i in deg and j in deg:
            net.add_edge(i, j, value=w,
                         color={"color": palette[cid[i]] if cid[i] == cid[j] else "#5b6b8a",
                                "opacity": 0.14 if cid[i] == cid[j] else 0.05})
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "interactions.html")
    net.write_html(path, notebook=False, open_browser=False)
    print("wrote", path)
    return path


def write_db(c, core, edges):
    c.execute("DROP TABLE IF EXISTS INTERACTS_WITH")
    c.execute("CREATE REL TABLE INTERACTS_WITH(FROM Persona TO Persona, weight DOUBLE)")
    for i, j, w in edges:
        c.execute("MATCH (a:Persona {id:$a}),(b:Persona {id:$b}) "
                  "CREATE (a)-[:INTERACTS_WITH {weight:$w}]->(b)",
                  {"a": core[i]["id"], "b": core[j]["id"], "w": w})
    print(f"materialized {len(edges):,} INTERACTS_WITH edges into the DB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=os.path.join(os.path.dirname(__file__), "persona_graph.kuzu"))
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--knn", type=int, default=10)
    ap.add_argument("--write-db", action="store_true")
    args = ap.parse_args()

    c = kuzu.Connection(kuzu.Database(args.db_path))
    c.execute("LOAD vector;")
    print(f"loading {args.n} personas …")
    core, gk, vals, traits = load(c, args.n)
    emb = np.array([r["emb"] for r in core], dtype=np.float32)
    print(f"  {len(core)} personas; generating candidate ties …")
    cand, norm = candidate_pairs(core, emb, knn=args.knn)
    edges = score(core, gk, norm, cand)
    print(f"  {len(cand):,} candidates -> {len(edges):,} interaction edges")
    G, comms, cid = detect(core, edges)
    big = [m for m in comms if len(m) >= 3]
    print(f"  {len(big)} communities (largest {len(comms[0])})")
    palette = _palette(len(comms))
    pos, big = clustered_layout(comms, cid, G)
    png, palette = render(core, comms, cid, G, pos, big, palette)
    html = render_html(core, edges, cid, palette, G, pos)
    prof = profile(core, vals, traits, comms, G)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "communities.json"), "w") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False, default=str)
    print("wrote", os.path.join(OUT, "communities.json"))
    if args.write_db:
        write_db(c, core, edges)
    print("\ntop communities:")
    for p in prof[:6]:
        st = p["top_states"][0][0] if p["top_states"] else "?"
        oc = p["top_occupations"][0][0] if p["top_occupations"] else "?"
        vv = ", ".join(v for v, _ in p["top_values"][:3])
        print(f"  #{p['community']:>2} n={p['size']:<4} {st:<16} {oc:<22} values: {vv}")


if __name__ == "__main__":
    main()
