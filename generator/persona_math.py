#!/usr/bin/env python3
"""
persona_math.py — executable reference implementation of the persona decision
model, RECONCILED TO v1.1 of PERSONA_MATHEMATICAL_MODEL.md. Standard library only.

Every function corresponds to an equation in the spec; the section tags below
point at the matching section. `evaluate_offer` composes Sections 4–11 into a
single acceptance probability P(accept | persona, hour), so the persona is a
*mathematical object*, not a template.

Parameter identifiability (see §14):
  Class A = literature-fixed   (α, γ, δ, Δ_max, φ)
  Class B = estimable          (λ_min/λ_max/s_λ, ψ, κ_ν, a, s, s_g, θ_g)
  Class C = design / by-fiat   (κ_K..κ_F, θ_e/θ_f/θ_n, b_m, b_s, ε)
"""
from math import exp, log, cos, pi, tanh
import random

# ---- helpers ---------------------------------------------------------------
def sigmoid(x): return 1.0/(1.0+exp(-x)) if x > -700 else 0.0
def clip(x, lo, hi): return max(lo, min(hi, x))
def clip01(x): return clip(x, 0.0, 1.0)

# ---- Sec. 2.4: cardinal log-money capital index ----------------------------
# c = clip( (ln m - ln m_min)/(ln m_max - ln m_min), 0, 1 ),  m = MPCE proxy (₹)
MPCE = {  # median monthly per-capita consumption proxy per NCCS class (₹)
    "A1":120000,"A2":90000,"A3":60000,"B1":45000,"B2":30000,"C1":20000,
    "C2":15000,"D":9000,"E1":7000,"E2":5500,"E3":4000}
M_MIN, M_MAX = 4000.0, 120000.0
def capital_index(nccs):                       # c ∈ [0,1], cardinal (§2.4)
    m = MPCE.get(nccs, 9000)
    return clip((log(m) - log(M_MIN)) / (log(M_MAX) - log(M_MIN)), 0.0, 1.0)

# ---- Sec. 4.1: loss aversion as a DISTRIBUTION over the capital base --------
# λ ~ Normal( λ̄(c), s_λ² ),  λ̄(c) = λ_min + (λ_max-λ_min)(1-c)   (Class B)
def loss_aversion_mean(c, lam_min=2.0, lam_max=3.0):
    return lam_min + (lam_max - lam_min)*(1.0 - c)
def loss_aversion(c, s_lambda=0.15, rng=None):     # one sample of λ
    lam = loss_aversion_mean(c)
    if rng is not None:
        lam += rng.gauss(0.0, s_lambda)
    return clip(lam, 1.0, 3.6)

# ---- Sec. 4.1: prospect value, money NORMALISED BY THE REFERENCE ρ ----------
# ṽ(x) = ((x-ρ)/ρ)^α  if x≥ρ ;  -λ·((ρ-x)/ρ)^α  if x<ρ   ⇒ dimensionless
def prospect_value(x, ref, lam, alpha=0.88):       # α Class A
    if ref <= 0: ref = 1.0
    d = (x - ref)/ref
    return (d**alpha) if d >= 0 else -lam*((-d)**alpha)

# ---- Sec. 4.2: Prelec probability weighting --------------------------------
def prob_weight(p, gamma=0.61):                    # γ Class A
    if p <= 0: return 0.0
    if p >= 1: return 1.0
    return exp(-((-log(p))**gamma))

# ---- Sec. 4.3: present-bias β(σ) -------------------------------------------
def present_bias(scarcity, beta_max=0.95, psi=0.60):   # ψ Class B
    return clip(beta_max - psi*scarcity, 0.25, 0.95)

# ---- Sec. 5: scarcity → bandwidth load (NORMALISED by WM span Q) ------------
# D_scar = (Δ_max/Q)·σ_s ∈ [0,0.33],  Δ_max≈13 (Class A), Q≈40
def D_scarcity(scarcity, delta_max=13.0, Q=40.0):
    return (delta_max/Q)*scarcity
def scarcity_iq_drop(scarcity, delta_max=13.0):    # reporting only (IQ points)
    return -delta_max*scarcity

# ---- Sec. 6: somatic + circadian load, BOUNDED multiplicative bandwidth -----
# Physical exertion accrues only DURING the shift [t0, t_end], then RECOVERS
# at rate ρ_rec afterward; this makes argmin_t B(t) land at a trade-specific
# hour (mason≈18, farmer≈13, vendor≈21) instead of trivially at the last hour.
# L(t) = D_phys + D_circ + D_scar ;  B(t) = B_max·exp(-L(t)) ∈ (0, B_max]
def D_phys(t, t0, t_end, delta_p, aging=False, rho_p=0.35, rho_rec=0.10):
    work = max(0.0, min(t, t_end) - t0)            # exertion accrued, frozen after shift
    exertion = delta_p*(exp(rho_p*work)-1.0) if aging else delta_p*work
    recovery = rho_rec*max(0.0, t - t_end)         # body recovers after the shift ends
    return max(0.0, exertion - recovery)
def D_circ(t, amp=0.35, phi=10.0):                 # φ Class A (10:00 alert peak)
    return amp*(1.0 - cos(2*pi*(t-phi)/24.0))/2.0
def load(t, t0=8.0, t_end=18.0, delta_p=0.05, aging=False, scarcity=0.0):
    return D_phys(t,t0,t_end,delta_p,aging) + D_circ(t) + D_scarcity(scarcity)
def bandwidth(t, t0=8.0, t_end=18.0, delta_p=0.05, aging=False, scarcity=0.0, B_max=1.0):
    return B_max*exp(-load(t,t0,t_end,delta_p,aging,scarcity))   # never saturates at 0
def peak_exhaustion_hour(t0=8.0, t_end=18.0, delta_p=0.05, aging=False, scarcity=0.0):
    # t* = argmin_t B(t) = argmax_t L(t) over the waking grid (§6 — doc/code agree)
    grid = [h/2 for h in range(8, 47)]             # 04:00–23:00 in 0.5h steps
    return min(grid, key=lambda t: bandwidth(t,t0,t_end,delta_p,aging,scarcity))

# occupation → (shift_start, shift_end); the schedule that drives t* emergently
SHIFTS = [
    (("farmer","cultivator","agri"), (5.0, 13.0)),
    (("mason","construction","labour"), (8.0, 18.0)),
    (("vendor","hawker"), (7.0, 21.0)),
    (("driver","rider","cab","auto","truck","tractor"), (8.0, 17.0)),
    (("domestic","dairy","livestock"), (6.0, 14.0)),
]
def shift_window(occupation, default=(9.0, 18.0)):
    o = occupation.lower()
    for keys, win in SHIFTS:
        if any(k in o for k in keys): return win
    return default

# ---- Sec. 7: dual-process gate, COLLAPSED to 2 free parameters --------------
# d = κ_K·stakes + κ_R·R - κ_T·tp - κ_F·(1-B) ;  p_S2 = σ( s_g·(d-θ_g) )
def deliberation_prob(B, reflective, stakes, time_pressure,
                      kK=1.2, kR=1.5, kT=1.4, kF=1.2,   # design priors (Class C)
                      s_g=2.5, theta_g=0.45):            # free slope/threshold (Class B)
    d = kK*stakes + kR*reflective - kT*time_pressure - kF*(1.0-B)
    return sigmoid(s_g*(d - theta_g))

# ---- Sec. 8: drift-diffusion with a START-POINT somatic bias (Cox–Miller) ---
# z0 = a·clip(0.5 + b_m·marker, .05, .95) ;  μ = κ_ν·U
# P(accept) = (e^{-2μ z0/s²}-1)/(e^{-2μ a/s²}-1) ,  μ≠0 ;  = z0/a , μ=0
def ddm_accept(U, boundary_a=1.0, drift_gain=1.2, noise=0.6,
               somatic_marker=0.0, b_m=0.30):
    a = max(boundary_a, 0.2)
    z0 = a*clip(0.5 + b_m*somatic_marker, 0.05, 0.95)   # start-point prior
    mu = drift_gain*U
    s2 = noise**2
    if abs(mu) < 1e-9:
        return clip01(z0/a)
    def E(x):
        z = -2.0*mu*x/s2
        return exp(z) if z < 700 else float("inf")
    num, den = E(z0)-1.0, E(a)-1.0
    if den == 0 or den == float("inf") or num == float("inf"):
        # numerical guard: fall back to the symmetric-start logistic limit
        return clip01(1.0/(1.0+exp(-2.0*mu*(a/2.0)/s2)))
    return clip01(num/den)

# ---- Sec. 10: novelty resistance (Carstensen) ------------------------------
def novelty_resistance(age, openness, educated, rural,
                       v0=0.35, v1=0.45, v2=0.20, v3=0.10, v4=0.05):
    return clip01(v0 + (v1 if age>=58 else 0.0) - v2*openness
                  - (v3 if educated else 0.0) + (v4 if rural else 0.0))
def horizon(age): return "Expansive" if age<30 else ("Constricted" if age>=58 else "Provisioning")

# ---- Sec. 9: precision-weighted belief / misinformation --------------------
def belief_update(mu_b, prec_b, e, prec_e):
    mu = (prec_b*mu_b + prec_e*e)/(prec_b+prec_e)
    return mu, prec_b+prec_e
def accept_claim(trust, ingroup_align, prior_prec, dist, k1=2.0, k2=1.5, k3=2.0):
    return sigmoid(k1*trust + k2*ingroup_align - k3*prior_prec*dist)

# ---- Sec. 11/13: build a decision_model from a persona's latents -----------
def decision_model(*, nccs, scarcity, age, occupation, reflective, openness,
                   educated, rural, prior_precision, t0=8.0, aging_manual=False,
                   ref_income=None, rng=None):
    c = capital_index(nccs)
    lam = loss_aversion(c, rng=rng)
    beta = present_bias(scarcity)
    manual = any(k in occupation for k in ("labour","mason","construction","farmer",
                 "cultivator","vendor","driver","domestic","dairy","rider"))
    delta_p = 0.08 if manual else 0.04
    aging = aging_manual or (manual and age>=45)
    t0_occ, t_end = shift_window(occupation, default=(t0, t0+9.0))
    t_star = peak_exhaustion_hour(t0_occ, t_end, delta_p, aging, scarcity)
    ref = ref_income if ref_income is not None else MPCE.get(nccs, 9000)
    return {
        "capital_index": round(c,3),
        "prospect": {"alpha":0.88, "lambda":round(lam,3), "lambda_mean":round(loss_aversion_mean(c),3),
                     "s_lambda":0.15, "gamma":0.61, "reference_income_inr": ref},
        "time": {"present_bias_beta": round(beta,3), "long_run_delta":0.97},
        "scarcity": {"state": round(scarcity,3),
                     "bandwidth_load_D_scar": round(D_scarcity(scarcity),3),
                     "iq_bandwidth_drop": round(scarcity_iq_drop(scarcity),1)},
        "somatic": {"shift_start": t0_occ, "shift_end": t_end, "depletion_rate": delta_p,
                    "convex_aging": aging, "peak_exhaustion_hour": t_star,
                    "bandwidth_at_peak": round(bandwidth(t_star,t0_occ,t_end,delta_p,aging,scarcity),3)},
        "dual_process": {"reflective_disposition": round(reflective,3)},
        "ddm": {"boundary_a":1.0, "drift_gain":1.2, "noise":0.6, "b_m":0.30},
        "belief": {"prior_precision": round(prior_precision,3)},
        "novelty_resistance_index": round(novelty_resistance(age,openness,educated,rural),3),
        "temporal_horizon": horizon(age),
        "U_weights": {"theta_econ":0.6, "theta_frame":0.2, "theta_novel":0.2},
    }

# ---- Sec. 11: the unified, DIMENSIONLESS & BOUNDED acceptance functional ----
def evaluate_offer(dm, *, monthly_cost_inr, benefit_value, prob_benefit=0.3,
                   hour=14.0, framing="shield", threatens_standing=False,
                   novelty=0.6, time_pressure=0.4, stakes=0.6,
                   inflation_shock=0.0, kappa_macro=0.55,
                   theta=(0.6,0.2,0.2), g_consult=0.05):
    """Return P(accept) for a recurring-cost offer, per Sections 4–11 (v1.1).

    U = θ_e·g_econ + θ_f·g_frame + θ_n·g_novel ∈ [-1,1], with each g ∈ [-1,1]
    and θ summing to 1, so P(accept) levels are interpretable.
    """
    pr = dm["prospect"]; ref = pr["reference_income_inr"]
    # MACRO COUPLING: inflation balloons effective loss aversion (§11)
    lam_eff = clip(pr["lambda"]*(1.0 + kappa_macro*inflation_shock), 1.0, 3.6)
    # economic term: discounted, prob-weighted gain + the recurring loss, both ρ-normalised
    beta = dm["time"]["present_bias_beta"]
    w = prob_weight(prob_benefit, pr["gamma"])
    v_gain = beta*w*prospect_value(ref+benefit_value, ref, lam_eff, pr["alpha"])
    v_loss = prospect_value(ref - monthly_cost_inr, ref, lam_eff, pr["alpha"])  # a loss (<0)
    g_econ  = tanh(v_gain + v_loss)                       # ∈ (-1,1)
    g_frame = +1.0 if framing=="shield" else (-1.0 if framing=="growth" else 0.0)
    g_novel = -dm["novelty_resistance_index"]*novelty     # ∈ [-1,0]
    th_e, th_f, th_n = theta
    U = clip(th_e*g_econ + th_f*g_frame + th_n*g_novel, -1.0, 1.0)
    # dual-process gate by bandwidth at this hour
    som = dm["somatic"]
    B = bandwidth(hour, som["shift_start"], som["shift_end"], som["depletion_rate"],
                  som["convex_aging"], dm["scarcity"]["state"])
    pS2 = deliberation_prob(B, dm["dual_process"]["reflective_disposition"], stakes, time_pressure)
    # System-2 path = start-point DDM on U; System-1 path = blunt avoid-heuristic
    somatic_marker = -1.0      # past-debt/agent memory ⇒ avoid-prior at the start point
    p_s2 = ddm_accept(U, dm["ddm"]["boundary_a"], dm["ddm"]["drift_gain"],
                      dm["ddm"]["noise"], somatic_marker, dm["ddm"]["b_m"])
    p_s1 = clip01(0.15 + 0.25*sigmoid(6.0*U))     # fast, mostly-reject under loss frame
    P = pS2*p_s2 + (1.0-pS2)*p_s1
    # SOCIAL DEFERENCE GATE (multiplicative, replaces the -∞ penalty)
    if threatens_standing:
        P = g_consult*P
    return {"P_accept": round(P, 3), "U": round(U,3), "bandwidth": round(B,3),
            "p_system2": round(pS2,3), "lambda_effective": round(lam_eff,3)}

# ---- demo ------------------------------------------------------------------
if __name__ == "__main__":
    import json
    rng = random.Random(2026)
    poor = decision_model(nccs="E1", scarcity=0.78, age=44, occupation="daily-wage labourer",
                          reflective=0.30, openness=0.40, educated=False, rural=True,
                          prior_precision=0.70, t0=8.0, rng=rng)
    rich = decision_model(nccs="B1", scarcity=0.15, age=34, occupation="software professional",
                          reflective=0.72, openness=0.78, educated=True, rural=False,
                          prior_precision=0.55, t0=9.0, rng=rng)
    print("POOR labourer decision_model:"); print(json.dumps(poor, indent=2, ensure_ascii=False))
    print("\ncardinal log-money capital index c (B1, C2, E3):",
          round(capital_index("B1"),3), round(capital_index("C2"),3), round(capital_index("E3"),3))
    print("λ̄(c) mean scaling (B1, C2, E3):",
          round(loss_aversion_mean(capital_index("B1")),2),
          round(loss_aversion_mean(capital_index("C2")),2),
          round(loss_aversion_mean(capital_index("E3")),2))
    print("\npeak-exhaustion hour t* (argmin B): poor labourer =", poor["somatic"]["peak_exhaustion_hour"],
          " software prof =", rich["somatic"]["peak_exhaustion_hour"])
    print("\n₹99/month micro-insurance — P(accept) across the day (poor labourer):")
    for h in [9, 12, 14, 17, 18, 20]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=h, framing="growth", time_pressure=0.5)
        print(f"  {int(h):02d}:00  P(accept)={r['P_accept']:.3f}  U={r['U']:+.3f}  "
              f"bandwidth={r['bandwidth']:.2f}  p_S2={r['p_system2']:.2f}")
    print("\nSame offer, 'shield' vs 'growth' framing at 18:00 (poor):")
    for fr in ["growth","shield"]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=18, framing=fr, time_pressure=0.5)
        print(f"  framing={fr:7s}  P(accept)={r['P_accept']:.3f}  U={r['U']:+.3f}")
    print("\nInflation shock (η=0.7) raises λ_eff and lowers acceptance (poor, 14:00):")
    for shock in [0.0, 0.7]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=14, framing="growth", inflation_shock=shock)
        print(f"  shock={shock}  λ_eff={r['lambda_effective']:.2f}  P(accept)={r['P_accept']:.3f}")
    print("\nSocial deference gate (offer threatens standing) collapses acceptance (poor, 14:00):")
    for thr in [False, True]:
        r = evaluate_offer(poor, monthly_cost_inr=99, benefit_value=20000, prob_benefit=0.1,
                           hour=14, framing="shield", threatens_standing=thr)
        print(f"  threatens_standing={str(thr):5s}  P(accept)={r['P_accept']:.3f}")
