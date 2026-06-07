"""Shared config: connection + behavioral-embedding feature spec."""
import os

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "personagraph")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

PERSONAS_DIR = os.environ.get(
    "PERSONAS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "personas"),
)

# Behavioral embedding: (json_path, min, max). Each feature min-max scaled to
# [0,1] with documented bounds (see generator/PERSONA_MATHEMATICAL_MODEL.md),
# then clamped. Fixed bounds keep the vector stable across incremental loads
# (no global population stats needed).
BEHAVIORAL_FEATURES = [
    ("identity.age",                                        18.0, 78.0),
    ("decision_model.capital_index",                         0.0,  1.0),
    ("decision_model.prospect.loss_aversion_lambda",         1.0,  4.0),
    ("decision_model.time.present_bias_beta",                0.25, 0.95),
    ("decision_model.scarcity.state",                        0.0,  1.0),
    ("decision_model.dual_process.reflective_disposition",   0.0,  1.0),
    ("decision_model.novelty_resistance_index",              0.0,  1.0),
    ("decision_model.somatic.peak_exhaustion_hour",          0.0, 24.0),
    ("decision_model.somatic.depletion_rate",               0.04, 0.08),
    ("decision_model.belief.prior_precision",                0.0,  1.0),
    ("contextual_dynamics.macro_environmental_sensitivity."
     "inflation_elasticity_coefficient",                     0.0,  1.0),
]

BEHAVIORAL_DIM = len(BEHAVIORAL_FEATURES)
