#!/usr/bin/env python3
"""
persona_math.py — executable reference implementation of the persona decision
model (see PERSONA_MATHEMATICAL_MODEL.md). Standard library only.

Every function corresponds to an equation in the spec. `evaluate_offer` composes
Sections 4–11 into a single acceptance probability P(accept | persona, hour),
so the persona is a *mathematical object*, not a template.
"""
from math import exp, log, cos, pi, tanh

# ---- helpers ---------------------------------------------------------------
def sigmoid(x): return 1.0/(1.0+exp(-x)) if x>-700 else 0.0
def clip(x, lo, hi): return max(lo, min(hi, x))
def clip01(x): return clip(x, 0.0, 1.0)

# ---- Sec. 2: SES → capital index ------------------------------------------
NCCS_LADDER = ["E3","E2","E1","D","C2","C1","B2","B1","A3","A2","A1"]
def capital_index(nccs):                       # c ∈ [0,1]
    return NCCS_LADDER.index(nccs)/(len(NCCS_LADDER)-1)

# ---- Sec. 4.1: loss aversion λ(c) -----------------------------------------
def loss_aversion(c, lam_min=2.0, lam_max=3.0, noise=0.0):
    return clip(lam_min + (lam_max-lam_min)*(1.0-c) + noise, 1.0, 3.6)

# ---- Sec. 4.1: prospect-theory value function -----------------------------
def prospect_value(x, ref, lam, alpha=0.88):
    d = x - ref
    return (d**alpha) if d >= 0 else -lam*((-d)**alpha)

# ---- Sec. 4.2: Prelec probability weighting -------------------------------
def prob_weight(p, gamma=0.65):
    if p <= 0: return 0.0
    if p >= 1: return 1.0
    return exp(-((-log(p))**gamma))

# ---- Sec. 4.3: present-bias β(σ) ------------------------------------------
def present_bias(scarcity, beta_max=0.95, psi=0.60):
    return clip(beta_max - psi*scarcity, 0.25, 0.95)

# ---- Sec. 5: scarcity cognitive-bandwidth tax -----------------------------
def scarcity_iq_drop(scarcity, delta_max=13.0):   # ΔIQ
    return -delta_max*scarcity
def D_scarcity(scarcity, b_s=0.25): return b_s*scarcity

# ---- Sec. 6: somatic + circadian bandwidth over the day -------------------
def D_phys(t, t0, delta_p, p=1.0, aging=False, rho_p=0.35):
    dt = max(0.0, t - t0)
    return delta_p*(exp(rho_p*dt)-1.0) if aging else delta_p*(dt**p)
def D_circ(t, amp=0.35, phi=10.0):
    return amp*(1.0 - cos(2*pi*(t-phi)/24.0))/2.0
def bandwidth(t, t0=8.0, delta_p=0.05, p=1.0, aging=False, scarcity=0.0):
    return clip01(1.0 - D_phys(t,t0,delta_p,p,aging) - D_circ(t) - D_scarcity(scarcity))
def peak_exhaustion_hour(t0=8.0, delta_p=0.05, p=1.0, aging=False, scarcity=0.0):
    grid = [h/2 for h in range(8, 47)]          # 04:00–23:00 in 0.5h steps
    return min(grid, key=lambda t: bandwidth(t,t0,delta_p,p,aging,scarcity))

# ---- Sec. 7: dual-process gate --------------------------------------------
def deliberation_prob(B, reflective, stakes, time_pressure,
                      w0=-0.5, wB=2.5, wR=1.5, wK=1.2, wT=1.4, wF=1.2, theta_B=0.45):
    return sigmoid(w0 + wB*(B-theta_B) + wR*reflective + wK*stakes
                   - wT*time_pressure - wF*(1.0-B))

# ---- Sec. 8: drift-diffusion choice probability ---------------------------
def ddm_accept(value_diff, boundary_a0=1.0, drift_gain=1.2, noise=0.6,
               somatic_marker=0.0, time_pressure=0.0, fatigue=0.0,
               zeta=0.4, scale=1.0, m=0.3):
    a = boundary_a0*(1.0 - zeta*clip(time_pressure+fatigue,0,1))
    a = max(a, 0.2)
    nu = drift_gain*value_diff/scale + m*somatic_marker
    return clip01(1.0/(1.0+exp(-2.0*nu*a/(noise**2))))

# ---- Sec. 10.2: novelty resistance (Carstensen) ---------------------------
def novelty_resistance(age, openness, educated, rural):
    return clip01(0.35 + (0.45 if age>=58 else 0.0) - 0.20*openness
                  - (0.10 if educated else 0.0) + (0.05 if rural else 0.0))
def horizon(age): return "Expansive" if age<30 else ("Constricted" if age>=58 else "Provisioning")

# ---- Sec. 9: precision-weighted belief / misinformation -------------------
def belief_update(mu_b, prec_b, e, prec_e):
    mu = (prec_b*mu_b + prec_e*e)/(prec_b+prec_e)
    return mu, prec_b+prec_e
def accept_claim(trust, ingroup_align, prior_prec, dist, k1=2.0, k2=1.5, k3=2.0):
    return sigmoid(k1*trust + k2*ingroup_align - k3*prior_prec*dist)

# ---- Sec. 11/13: build a decision_model from a persona's latents ----------
def decision_model(*, nccs, scarcity, age, occupation, reflective, openness,
                   educated, rural, prior_precision, t0=8.0, aging_manual=False,
                   ref_income=None):
    c = capital_index(nccs)
    lam = loss_aversion(c)
    beta = present_bias(scarcity)
    # somatic depletion rate scales with manual physical load
    manual = any(k in occupation for k in ("labour","mason","construction","farmer",
                 "cultivator","vendor","driver","domestic","dairy","rider"))
    delta_p = 0.08 if manual else 0.04
    p_exp = 1.0; aging = aging_manual or (manual and age>=45)
    t_star = peak_exhaustion_hour(t0, delta_p, p_exp, aging, scarcity)
    ref = ref_income if ref_income is not None else {
        "A1":120000,"A2":90000,"A3":60000,"B1":45000,"B2":30000,"C1":20000,
        "C2":15000,"D":9000,"E1":7000,"E2":5500,"E3":4000}.get(nccs, 9000)
    return {
        "capital_index": round(c,3),
        "prospect": {"alpha":0.88, "lambda":round(lam,3), "gamma":0.65,
                     "reference_income_inr": ref},
        "time": {"present_bias_beta": round(beta,3), "long_run_delta":0.97},
        "scarcity": {"state": round(scarcity,3),
                     "iq_bandwidth_drop": round(scarcity_iq_drop(scarcity),1)},
        "somatic": {"shift_start": t0, "depletion_rate": delta_p, "convex": aging,
                    "peak_exhaustion_hour": t_star},
        "dual_process": {"reflective_disposition": round(reflective,3)},
        "ddm": {"boundary_a0":1.0, "drift_gain":1.2, "noise":0.6},
        "belief": {"prior_precision": round(prior_precision,3)},
        "novelty_resistance_index": round(novelty_resistance(age,openness,educated,rural),3),
        "temporal_horizon": horizon(age),
    }

# ---- Sec. 11: the unified acceptance functional ---------------------------
def evaluate_offer(dm, *, monthly_cost_inr, benefit_value, prob_benefit=0.3,
                   hour=14.0, framing="shield", threatens_standing=False,
                   novelty=0.6, time_pressure=0.4, stakes=0.6,
                   inflation_shock=0.0, kappa_macro=0.55):
    """Return P(accept) for a recurring-cost offer, per Sections 4–11."""
    pr = dm["prospect"]; ref = pr["reference_income_inr"]
    lam = pr["lambda"]*(1.0 + kappa_macro*inflation_shock)           # macro coupling
    # prospect value of the recurring loss (cost) vs the weighted, discounted benefit
    v_cost = prospect_value(ref - monthly_cost_inr, ref, lam, pr["alpha"])   # a loss
    v_gain = present_bias_then_value(dm, benefit_value, ref, prob_benefit)
    frame = +0.25 if framing=="shield" else (-0.30 if framing=="growth" else 0.0)
    social = 8.0 if threatens_standing else 0.0          # deference penalty (huge)
    nov = novelty*dm["novelty_resistance_index"]
    U = (v_gain + v_cost)/max(abs(ref),1) + frame - nov - social     # normalized
    # dual-process gate by bandwidth at this hour
    som = dm["somatic"]
    B = bandwidth(hour, som["shift_start"], som["depletion_rate"], 1.0,
                  som["convex"], dm["scarcity"]["state"])
    fatigue = 1.0 - B
    pS2 = deliberation_prob(B, dm["dual_process"]["reflective_disposition"], stakes, time_pressure)
    # System-2 path = DDM on U; System-1 path = blunt avoid-heuristic for loss-framed offers
    somatic_marker = -1.0      # past debt/agent memory ⇒ avoid bias
    p_s2 = ddm_accept(U, dm["ddm"]["boundary_a0"], dm["ddm"]["drift_gain"],
                      dm["ddm"]["noise"], somatic_marker, time_pressure, fatigue)
    p_s1 = clip01(0.15 + 0.25*sigmoid(U))     # fast, mostly-reject under loss frame
    return {"P_accept": round(pS2*p_s2 + (1-pS2)*p_s1, 3),
            "bandwidth": round(B,3), "p_system2": round(pS2,3),
            "lambda_effective": round(lam,3)}

def present_bias_then_value(dm, benefit_value, ref, prob_benefit):
    # discounted, probability-weighted gain (benefit accrues in the future)
    beta = dm["time"]["present_bias_beta"]
    w = prob_weight(prob_benefit, dm["prospect"]["gamma"])
    return beta*w*prospect_value(ref+benefit_value, ref, dm["prospect"]["lambda"], dm["prospect"]["alpha"])

# ---- demo ------------------------------------------------------------------
if __name__ == "__main__":
    # A poor rural daily-wage persona (NCCS E1) vs an affluent professional (B1)
    poor = decision_model(nccs="E1", scarcity=0.78, age=44, occupation="daily-wage labourer",
                          reflective=0.30, openness=0.40, educated=False, rural=True,
                          prior_precision=0.70, t0=8.0)
    rich = decision_model(nccs="B1", scarcity=0.15, age=34, occupation="software professional",
                          reflective=0.72, openness=0.78, educated=True, rural=False,
                          prior_precision=0.55, t0=9.0)
    import json
    print("POOR labourer decision_model:"); print(json.dumps(poor, indent=2, ensure_ascii=False))
    print("\nλ scaling check (B1, C2, E3):",
          round(loss_aversion(capital_index("B1")),2),
          round(loss_aversion(capital_index("C2")),2),
          round(loss_aversion(capital_index("E3")),2))
    print("\n₹99/month micro-insurance — P(accept) across the day (poor labourer):")
    for h in [9, 12, 14, 17, 18, 20]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=h, framing="growth", time_pressure=0.5)
        print(f"  {int(h):02d}:00  P(accept)={r['P_accept']:.3f}  bandwidth={r['bandwidth']:.2f}  p_S2={r['p_system2']:.2f}")
    print("\nSame offer, 'shield' framing vs 'growth' framing at 18:00 (poor):")
    for fr in ["growth","shield"]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=18, framing=fr, time_pressure=0.5)
        print(f"  framing={fr:7s}  P(accept)={r['P_accept']:.3f}")
    print("\nInflation shock (η=0.7) raises effective λ and lowers acceptance (poor, 14:00):")
    for shock in [0.0, 0.7]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=14, framing="growth", inflation_shock=shock)
        print(f"  shock={shock}  λ_eff={r['lambda_effective']:.2f}  P(accept)={r['P_accept']:.3f}")
