#!/usr/bin/env python3
"""Build the persona knowledge graph as an embedded **Kuzu** database.

Streams persona JSONL -> Parquet (columnar) -> Kuzu COPY (bulk) -> HNSW vector
index, then optionally packages the DB folder into a single archive for
publishing as a GitHub Release asset. No server, no subscription, no local
hosting required.

    python build_kuzu.py --source sample
    python build_kuzu.py --source shards --shards all --package
"""
import argparse
import glob
import os
import shutil
import tarfile
import tempfile
import time

import pyarrow as pa
import pyarrow.parquet as pq

import config
from persona_fields import iter_rows

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "persona_graph.kuzu")

# Node tables: label -> DDL column spec (order matters; parquet matches it).
NODE_DDL = {
    "Persona": (
        "id STRING, name STRING, age INT64, gender STRING, setting STRING, "
        "portrait STRING, capital_index DOUBLE, loss_aversion_lambda DOUBLE, "
        "present_bias_beta DOUBLE, scarcity_state DOUBLE, "
        "reflective_disposition DOUBLE, novelty_resistance_index DOUBLE, "
        "peak_exhaustion_hour DOUBLE, inflation_elasticity DOUBLE, "
        "emb FLOAT[11], PRIMARY KEY(id)"
    ),
}
DIM_LABELS = [
    "State", "Region", "Language", "Dialect", "Religion", "Community",
    "Occupation", "OccupationTier", "EducationLevel", "NccsClass",
    "IncomeBand", "Value", "Trait", "Gatekeeper", "TemporalHorizon",
]

# Persona->Dimension single-valued rels: rel -> (target_label, row_key)
SINGLE_RELS = {
    "LIVES_IN": ("State", "state"),
    "SPEAKS": ("Language", "language"),
    "PRACTICES": ("Religion", "religion"),
    "BELONGS_TO": ("Community", "community"),
    "WORKS_AS": ("Occupation", "occupation"),
    "HAS_EDUCATION": ("EducationLevel", "education"),
    "IN_CLASS": ("NccsClass", "class_nccs"),
    "HAS_INCOME_BAND": ("IncomeBand", "income_band"),
    "HAS_HORIZON": ("TemporalHorizon", "temporal_horizon"),
    "USES_DIALECT": ("Dialect", "dialect"),  # nullable
}
# Persona->Dimension multi-valued rels: rel -> (target_label, row_list_key)
MULTI_RELS = {
    "EXHIBITS": ("Trait", "traits"),
    "TRUSTS": ("Gatekeeper", "gatekeepers"),
}

PERSONA_COLS = [
    "id", "name", "age", "gender", "setting", "portrait", "capital_index",
    "loss_aversion_lambda", "present_bias_beta", "scarcity_state",
    "reflective_disposition", "novelty_resistance_index",
    "peak_exhaustion_hour", "inflation_elasticity",
]
PERSONA_SCHEMA = pa.schema(
    [(c, pa.string() if c in ("id", "name", "gender", "setting", "portrait")
      else pa.int64() if c == "age" else pa.float64()) for c in PERSONA_COLS]
    + [("emb", pa.list_(pa.float32(), 11))]
)


class BatchWriter:
    """Buffers rows and flushes Parquet row groups to bound memory."""
    def __init__(self, path, schema, batch=50000):
        self.writer = pq.ParquetWriter(path, schema)
        self.schema = schema
        self.batch = batch
        self.cols = [[] for _ in schema.names]
        self.n = 0

    def add(self, values):
        for i, v in enumerate(values):
            self.cols[i].append(v)
        self.n += 1
        if self.n >= self.batch:
            self.flush()

    def flush(self):
        if self.n:
            arrs = [pa.array(c, type=self.schema.field(i).type)
                    for i, c in enumerate(self.cols)]
            self.writer.write_table(pa.table(arrs, schema=self.schema))
            self.cols = [[] for _ in self.schema.names]
            self.n = 0

    def close(self):
        self.flush()
        self.writer.close()


def export_parquet(paths, pdir, limit=None):
    """Stream personas into Parquet files; return dimension/edge sets."""
    rel2 = pa.schema([("f", pa.string()), ("t", pa.string())])
    hv_schema = pa.schema([("f", pa.string()), ("t", pa.string()),
                           ("rank", pa.int64()), ("shows_up_as", pa.string())])

    persona_w = BatchWriter(os.path.join(pdir, "Persona.parquet"), PERSONA_SCHEMA)
    single_w = {r: BatchWriter(os.path.join(pdir, f"{r}.parquet"), rel2)
                for r in SINGLE_RELS}
    multi_w = {r: BatchWriter(os.path.join(pdir, f"{r}.parquet"), rel2)
               for r in MULTI_RELS}
    hv_w = BatchWriter(os.path.join(pdir, "HOLDS_VALUE.parquet"), hv_schema)

    dims = {lbl: set() for lbl in DIM_LABELS}
    state_region, occ_tier = set(), set()
    n, t0 = 0, time.time()

    for row in iter_rows(paths, limit=limit):
        persona_w.add([row[c] for c in PERSONA_COLS] + [row["embedding_behavioral"]])
        # dimensions
        for lbl, key in (("State", "state"), ("Region", "region"),
                         ("Language", "language"), ("Religion", "religion"),
                         ("Community", "community"), ("Occupation", "occupation"),
                         ("OccupationTier", "occupation_tier"),
                         ("EducationLevel", "education"), ("NccsClass", "class_nccs"),
                         ("IncomeBand", "income_band"),
                         ("TemporalHorizon", "temporal_horizon")):
            if row[key]:
                dims[lbl].add(row[key])
        if row["dialect"]:
            dims["Dialect"].add(row["dialect"])
        for t in row["traits"]:
            dims["Trait"].add(t)
        for g in row["gatekeepers"]:
            dims["Gatekeeper"].add(g)
        for cv in row["values"]:
            dims["Value"].add(cv["value"])
        if row["state"] and row["region"]:
            state_region.add((row["state"], row["region"]))
        if row["occupation"] and row["occupation_tier"]:
            occ_tier.add((row["occupation"], row["occupation_tier"]))
        # persona->dim rels
        for rel, (_, key) in SINGLE_RELS.items():
            if row[key]:
                single_w[rel].add([row["id"], row[key]])
        for rel, (_, lkey) in MULTI_RELS.items():
            for v in row[lkey]:
                multi_w[rel].add([row["id"], v])
        for cv in row["values"]:
            hv_w.add([row["id"], cv["value"], cv["rank"], cv["shows_up_as"]])
        n += 1
        if n % 100000 == 0:
            print(f"  exported {n:,} ({n/(time.time()-t0):,.0f}/s)")

    persona_w.close()
    for w in single_w.values():
        w.close()
    for w in multi_w.values():
        w.close()
    hv_w.close()

    # dimension node parquet
    for lbl, names in dims.items():
        pq.write_table(pa.table({"name": pa.array(sorted(names))}),
                       os.path.join(pdir, f"{lbl}.parquet"))
    pq.write_table(
        pa.table({"f": [a for a, _ in state_region], "t": [b for _, b in state_region]}),
        os.path.join(pdir, "IN_REGION.parquet"))
    pq.write_table(
        pa.table({"f": [a for a, _ in occ_tier], "t": [b for _, b in occ_tier]}),
        os.path.join(pdir, "HAS_TIER.parquet"))
    print(f"exported {n:,} personas in {time.time()-t0:,.1f}s")
    return n


def build_db(pdir, db_path, with_vector=True):
    import kuzu
    if os.path.exists(db_path):
        shutil.rmtree(db_path) if os.path.isdir(db_path) else os.remove(db_path)
    db = kuzu.Database(db_path)
    c = kuzu.Connection(db)
    for lbl, ddl in NODE_DDL.items():
        c.execute(f"CREATE NODE TABLE {lbl}({ddl})")
    for lbl in DIM_LABELS:
        c.execute(f"CREATE NODE TABLE {lbl}(name STRING, PRIMARY KEY(name))")
    for rel, (tgt, _) in SINGLE_RELS.items():
        c.execute(f"CREATE REL TABLE {rel}(FROM Persona TO {tgt})")
    for rel, (tgt, _) in MULTI_RELS.items():
        c.execute(f"CREATE REL TABLE {rel}(FROM Persona TO {tgt})")
    c.execute("CREATE REL TABLE HOLDS_VALUE(FROM Persona TO Value, rank INT64, shows_up_as STRING)")
    c.execute("CREATE REL TABLE IN_REGION(FROM State TO Region)")
    c.execute("CREATE REL TABLE HAS_TIER(FROM Occupation TO OccupationTier)")

    t0 = time.time()
    for lbl in list(NODE_DDL) + DIM_LABELS:
        c.execute(f"COPY {lbl} FROM '{os.path.join(pdir, lbl + '.parquet')}'")
    for rel in list(SINGLE_RELS) + list(MULTI_RELS) + ["HOLDS_VALUE", "IN_REGION", "HAS_TIER"]:
        c.execute(f"COPY {rel} FROM '{os.path.join(pdir, rel + '.parquet')}'")
    print(f"COPY complete in {time.time()-t0:,.1f}s")

    if with_vector:
        t0 = time.time()
        c.execute("INSTALL vector; LOAD vector;")
        c.execute("CALL CREATE_VECTOR_INDEX('Persona', 'persona_behavioral', 'emb')")
        print(f"vector index built in {time.time()-t0:,.1f}s")
    del c, db


def package(db_path, out_path=None):
    out_path = out_path or db_path + ".tar.gz"
    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(db_path, arcname=os.path.basename(db_path))
    size = os.path.getsize(out_path) / 1e6
    print(f"packaged -> {out_path} ({size:,.1f} MB)")
    return out_path


def resolve_paths(args):
    if args.source == "sample":
        return [os.path.join(config.PERSONAS_DIR, "sample_personas.jsonl")]
    shards = sorted(glob.glob(os.path.join(config.PERSONAS_DIR, "personas_*.jsonl")))
    if args.shards in (None, "all"):
        return shards
    lo, _, hi = args.shards.partition("-")
    lo = int(lo)
    hi = int(hi) if hi else lo
    return [p for p in shards if lo <= int(os.path.basename(p)[9:14]) <= hi]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sample", "shards"], default="sample")
    ap.add_argument("--shards", help="e.g. '0', '0-9', or 'all'")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--db-path", default=DEFAULT_DB)
    ap.add_argument("--package", action="store_true", help="also create .tar.gz")
    ap.add_argument("--no-vector-index", action="store_true")
    args = ap.parse_args()

    paths = resolve_paths(args)
    print(f"building Kuzu graph from {len(paths)} file(s) -> {args.db_path}")
    pdir = tempfile.mkdtemp(prefix="persona_parquet_")
    try:
        export_parquet(paths, pdir, limit=args.limit)
        build_db(pdir, args.db_path, with_vector=not args.no_vector_index)
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
    if args.package:
        package(args.db_path)
    print("done")


if __name__ == "__main__":
    main()
