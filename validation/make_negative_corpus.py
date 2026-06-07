#!/usr/bin/env python3
"""
make_negative_corpus.py — build the L0 anti-rot fixture.

Takes clean personas from the factory and applies ONE targeted mutation each, so
every record is guaranteed to trip exactly one structural-validator rule. The
resulting fixtures/negative_corpus.jsonl is what test_invariants.py replays to
prove the validator still catches every known failure class (prevents a silently
broken validator from passing a release).

Each record carries a `_expect` key naming the rule it must trigger; `_expect` is
stripped before the persona is handed to the validator.

Run once (and re-run whenever a new validator rule is added):
  python3 validation/make_negative_corpus.py
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(HERE), "generator")
sys.path.insert(0, GEN)
import persona_factory as pf  # noqa: E402


def clean(seed):
    import random
    pf.random.seed(seed)
    return pf.build_persona()


def mutate(p, rule):
    p = copy.deepcopy(p)
    idn = p["identity"]; bg = p["background"]
    if rule == "education_x_manual_labour":
        idn["occupation"] = "mason"; idn["occupation_tier"] = "manual"
        idn["education"] = "a graduate degree"
    elif rule == "corporate_role_low_education":
        idn["occupation"] = "software professional"; idn["occupation_tier"] = "corporate"
        idn["education"] = "Class 10"
    elif rule == "corporate_vocab_outside_corporate":
        idn["occupation_tier"] = "manual"
        p["voice"]["trade_vocabulary"] = ["north-star metric", "kpi", "alignment"]
    elif rule == "corporate_psych_in_manual":
        idn["occupation_tier"] = "manual"
        p["motivations"] = {"hidden": "battling imposter syndrome about intellectual mastery"}
    elif rule == "surname_geography":
        p["name"] = "Ramesh Reddy"; idn["religion"] = "Hindu"; idn["state"] = "Uttar Pradesh"
    elif rule == "gendered_string_bleed":
        idn["gender"] = "M"
        p["contextual_dynamics"] = {"network": "active in the women's savings group"}
    elif rule == "cross_trade_metaphor":
        idn["occupation"] = "mason"
        p["cognitive_architecture"] = {"heuristic": "measure twice, cut once"}
    elif rule == "unmarried_homemaker":
        idn["occupation"] = "homemaker"; bg["marital_status"] = "unmarried"
    elif rule == "childless_child_reference":
        bg["children"] = 0
        p["motivations"] = {"explicit_drivers": ["the children's schooling"]}
    elif rule == "gendered_pronoun_bleed":
        idn["gender"] = "M"
        p["psychological_paradoxes"] = {"note": "she keeps her plans to herself"}
    elif rule == "occupation_artifact_bleed":
        idn["occupation"] = "kirana shopkeeper"
        p["background"]["anchoring_memory"] = "saving up for the first sewing machine"
    elif rule == "null_geography":
        idn["state"] = "Other"
    elif rule == "schema_incomplete":
        p.pop("voice", None)
    else:
        raise ValueError(rule)
    p["_expect"] = rule
    return p


RULES = [
    "education_x_manual_labour", "corporate_role_low_education",
    "corporate_vocab_outside_corporate", "corporate_psych_in_manual",
    "surname_geography", "gendered_string_bleed", "cross_trade_metaphor",
    "unmarried_homemaker", "childless_child_reference", "gendered_pronoun_bleed",
    "occupation_artifact_bleed", "null_geography", "schema_incomplete",
]


def main():
    out = os.path.join(HERE, "fixtures", "negative_corpus.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for i, rule in enumerate(RULES):
            base = clean(1000 + i)
            f.write(json.dumps(mutate(base, rule), ensure_ascii=False) + "\n")
    print(f"wrote {len(RULES)} negative fixtures -> {out}")


if __name__ == "__main__":
    main()
