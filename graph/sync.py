#!/usr/bin/env python3
"""Incremental sync: hash every persona file, reload only changed/new ones.

State lives in graph/.sync_state.json (filename -> sha256). Because the loader
is idempotent (MERGE on stable keys), re-ingesting a changed shard simply
upserts its personas. Run locally via a git hook or in CI on push.

    python sync.py            # sync all shards + sample
    python sync.py --schema   # also (re)apply constraints/index first
"""
import argparse
import glob
import hashlib
import json
import os

import build_graph
import config

STATE_FILE = os.path.join(os.path.dirname(__file__), ".sync_state.json")


def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(buf):
            h.update(chunk)
    return h.hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as fh:
            return json.load(fh)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as fh:
        json.dump(state, fh, indent=2)


def discover():
    files = sorted(glob.glob(os.path.join(config.PERSONAS_DIR, "personas_*.jsonl")))
    sample = os.path.join(config.PERSONAS_DIR, "sample_personas.jsonl")
    if os.path.exists(sample):
        files.append(sample)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", action="store_true")
    args = ap.parse_args()

    state = load_state()
    files = discover()
    changed = [f for f in files if state.get(os.path.basename(f)) != sha256(f)]

    if not changed and not args.schema:
        print("nothing changed; graph already in sync")
        return

    driver = build_graph.connect()
    driver.verify_connectivity()
    try:
        if args.schema:
            build_graph.apply_schema(driver)
        if changed:
            print(f"syncing {len(changed)} changed file(s):")
            for f in changed:
                print(f"  - {os.path.basename(f)}")
            build_graph.load_files(driver, changed)
            for f in changed:
                state[os.path.basename(f)] = sha256(f)
            save_state(state)
        print("sync complete")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
