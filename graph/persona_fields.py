"""Persona JSON -> flat row + behavioral embedding. No DB dependency, shared
by both the Kuzu (hosted/free) and Neo4j (optional local) loaders."""
import json

import config


def get_path(obj, dotted, default=None):
    cur = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def behavioral_vector(persona):
    """11-dim min-max normalized vector from decision_model (see config)."""
    vec = []
    for path, lo, hi in config.BEHAVIORAL_FEATURES:
        raw = get_path(persona, path)
        if raw is None:
            vec.append(0.5)
            continue
        scaled = (float(raw) - lo) / (hi - lo) if hi > lo else 0.5
        vec.append(round(min(1.0, max(0.0, scaled)), 6))
    return vec


def build_row(persona):
    ident = persona.get("identity", {})
    gatekeepers = get_path(
        persona,
        "contextual_dynamics.social_capital_trust_network.institutional_gatekeepers",
        default=[],
    ) or []
    values = []
    for cv in persona.get("core_values", []) or []:
        if cv.get("value"):
            values.append({
                "value": cv.get("value"),
                "rank": cv.get("rank"),
                "shows_up_as": cv.get("shows_up_as"),
            })
    return {
        "id": persona["id"],
        "name": persona.get("name"),
        "age": ident.get("age"),
        "gender": ident.get("gender"),
        "setting": ident.get("setting"),
        "portrait": persona.get("portrait"),
        "state": ident.get("state"),
        "region": ident.get("region"),
        "language": ident.get("language"),
        "dialect": ident.get("dialect"),
        "religion": ident.get("religion"),
        "community": ident.get("community"),
        "occupation": ident.get("occupation"),
        "occupation_tier": ident.get("occupation_tier"),
        "education": ident.get("education"),
        "class_nccs": ident.get("class_nccs"),
        "income_band": ident.get("income_band"),
        "temporal_horizon": get_path(
            persona, "decision_model.temporal_horizon", default="Unknown"),
        "capital_index": get_path(persona, "decision_model.capital_index"),
        "loss_aversion_lambda": get_path(
            persona, "decision_model.prospect.loss_aversion_lambda"),
        "present_bias_beta": get_path(
            persona, "decision_model.time.present_bias_beta"),
        "scarcity_state": get_path(persona, "decision_model.scarcity.state"),
        "reflective_disposition": get_path(
            persona, "decision_model.dual_process.reflective_disposition"),
        "novelty_resistance_index": get_path(
            persona, "decision_model.novelty_resistance_index"),
        "peak_exhaustion_hour": get_path(
            persona, "decision_model.somatic.peak_exhaustion_hour"),
        "inflation_elasticity": get_path(
            persona,
            "contextual_dynamics.macro_environmental_sensitivity."
            "inflation_elasticity_coefficient"),
        "traits": persona.get("dominant_traits", []) or [],
        "gatekeepers": gatekeepers,
        "values": values,
        "embedding_behavioral": behavioral_vector(persona),
    }


def iter_rows(paths, limit=None):
    n = 0
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield build_row(json.loads(line))
                n += 1
                if limit and n >= limit:
                    return
