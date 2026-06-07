#!/usr/bin/env python3
"""
validate_personas.py — flag structural anomalies in a persona corpus.

Catches the cross-archetype contamination class (the "graduate-degree mason with
corporate imposter-syndrome" failure) and name-geography errors. Reports a
pass/fail count per rule plus up to a few examples each.

Usage:
  python3 validate_personas.py personas/                 # a dir of *.jsonl shards
  python3 validate_personas.py personas/ --examples 3
  python3 validate_personas.py personas/ --fail-on-any   # exit 1 if any anomaly
"""
import argparse, glob, json, os, re, sys

MANUAL_OCC={"agricultural labourer","small farmer","daily-wage labourer","dairy/livestock worker","domestic worker",
 "street vendor","construction worker","delivery rider","mason","auto/cab driver","tractor/truck driver","factory operator"}
CORP_OCC={"software professional","business owner","bank employee","doctor"}
GRAD={"a graduate degree","a postgraduate degree"}
LOWED={"no formal schooling","some schooling","Class 10"}
CORP_VOCAB={"target","scope","alignment","north-star metric","north star","follow-up","kpi","okrs"}
CORP_PSYCH={"imposter syndrome","intellectual mastery","north-star","north star","scalability","leverage"}
HINDI_BELT={"Uttar Pradesh","Bihar","Madhya Pradesh","Rajasthan","Haryana","Delhi","Jharkhand"}
SOUTH_SURNAMES={"Reddy","Naidu","Gowda","Shetty","Iyer","Iyengar","Nair","Menon","Pillai","Hegde","Rao","Chowdary"}

RULES=[
 ("education_x_manual_labour","Graduate/PG degree held by a manual-labour occupation"),
 ("corporate_role_low_education","Corporate role (software/doctor/bank/business) with below-Class-12 education"),
 ("corporate_vocab_outside_corporate","Corporate/tech jargon in a non-corporate persona's trade vocabulary"),
 ("corporate_psych_in_manual","Corporate psychology (imposter syndrome / intellectual mastery) in a manual/skilled role"),
 ("surname_geography","Southern surname on a Hindu persona in the Hindi-belt (or vice-versa)"),
 ("gendered_string_bleed","Female-specific string (e.g. women's savings group) on a male persona"),
 ("cross_trade_metaphor","Tailoring 'measure twice, cut once' metaphor on a non-tailor"),
 ("unmarried_homemaker","Persona marked homemaker but unmarried"),
 ("childless_child_reference","Child/childcare reference on a persona with 0 children"),
 ("gendered_pronoun_bleed","Female pronoun (she/her) on a male persona's free text"),
 ("occupation_artifact_bleed","Tailor-specific artifact (sewing machine) on a non-tailor"),
 ("null_geography","State / region / language left as 'Other'"),
 ("schema_incomplete","Missing one of the required top-level fields"),
]
REQ=["id","name","identity","portrait","background","dominant_traits","quirks","core_values","motivations",
 "stress_and_coping","political_leaning","daily_rhythm","voice","eight_pillars","cognitive_architecture","agent_guardrails","confidence"]

def tier_of(p):  # prefer explicit tier; else infer
    return p.get("identity",{}).get("occupation_tier") or ("manual" if p.get("identity",{}).get("occupation") in MANUAL_OCC else "?")

def check(p):
    flags=[]; idn=p.get("identity",{}); occ=idn.get("occupation",""); edu=idn.get("education",""); tier=tier_of(p)
    if edu in GRAD and occ in MANUAL_OCC: flags.append("education_x_manual_labour")
    if occ in CORP_OCC and edu in LOWED: flags.append("corporate_role_low_education")
    vocab=" ".join(p.get("voice",{}).get("trade_vocabulary",[])).lower()
    if tier!="corporate" and any(w in vocab for w in CORP_VOCAB): flags.append("corporate_vocab_outside_corporate")
    motiv=json.dumps(p.get("motivations",{})).lower()
    if tier in("manual","skilled") and any(w in motiv for w in CORP_PSYCH): flags.append("corporate_psych_in_manual")
    sn=p.get("name","").split()[-1] if p.get("name") else ""
    if idn.get("religion")=="Hindu" and idn.get("state") in HINDI_BELT and sn in SOUTH_SURNAMES: flags.append("surname_geography")
    blob=json.dumps(p).lower()
    if idn.get("gender")=="M" and "women's savings group" in blob: flags.append("gendered_string_bleed")
    if "tailor" not in occ and "measure twice, cut once" in json.dumps(p): flags.append("cross_trade_metaphor")
    if occ=="homemaker" and p.get("background",{}).get("marital_status")=="unmarried": flags.append("unmarried_homemaker")
    kids=p.get("background",{}).get("children")
    child_scope=json.dumps({k:p.get(k) for k in ("motivations","daily_rhythm","psychological_paradoxes","cognitive_architecture","contextual_dynamics")}).lower()
    if kids==0 and re.search(r"child's|children's|childcare|the kids|for the kids|kids'",child_scope): flags.append("childless_child_reference")
    free_text=json.dumps({k:p.get(k) for k in ("background","psychological_paradoxes","cognitive_architecture","contextual_dynamics","stress_and_coping","motivations")}).lower()
    if idn.get("gender")=="M" and re.search(r"\bher\b|\bshe\b",free_text): flags.append("gendered_pronoun_bleed")
    if "tailor" not in occ and "sewing machine" in json.dumps(p).lower(): flags.append("occupation_artifact_bleed")
    if idn.get("state")=="Other" or idn.get("region")=="Other" or idn.get("language")=="Other": flags.append("null_geography")
    if any(k not in p for k in REQ): flags.append("schema_incomplete")
    return flags

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--examples",type=int,default=2); ap.add_argument("--fail-on-any",action="store_true")
    a=ap.parse_args()
    files=sorted(glob.glob(os.path.join(a.path,"*.jsonl"))) if os.path.isdir(a.path) else [a.path]
    if not files: sys.exit("no .jsonl files found at "+a.path)
    total=0; counts={r:0 for r,_ in RULES}; egs={r:[] for r,_ in RULES}
    for fn in files:
        for line in open(fn,encoding="utf-8"):
            line=line.strip()
            if not line: continue
            p=json.loads(line); total+=1
            for f in check(p):
                counts[f]+=1
                if len(egs[f])<a.examples: egs[f].append(f"{p.get('name')} — {p.get('identity',{}).get('occupation')}, {p.get('identity',{}).get('education')}, {p.get('identity',{}).get('state')}")
    anomalies=sum(counts.values())
    print(f"\nValidated {total:,} personas across {len(files)} file(s)\n"+"-"*64)
    for r,desc in RULES:
        status="OK  " if counts[r]==0 else "FAIL"
        print(f"[{status}] {counts[r]:>6}  {desc}")
        for e in egs[r]: print(f"            e.g. {e}")
    print("-"*64)
    print(f"TOTAL anomalies: {anomalies}  ({anomalies/max(total,1)*100:.3f}% of personas)")
    print("RESULT:", "PASS — corpus clean" if anomalies==0 else f"{anomalies} anomalies to fix")
    if a.fail_on_any and anomalies: sys.exit(1)

if __name__=="__main__": main()
