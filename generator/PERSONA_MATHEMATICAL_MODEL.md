# The Mathematical Model of Persona Generation

This document specifies the persona engine as a **formal probabilistic and computational model**, not a template script. A persona is a sample from a defined joint distribution; every cognitive and behavioural parameter is given by an explicit equation grounded in the literature (prospect theory, hyperbolic discounting, scarcity theory, drift-diffusion, predictive coding, socioemotional selectivity). The reference implementation is `persona_math.py`.

---

## 0. Notation

| Symbol | Meaning |
|---|---|
| `S, U, Λ, Rel, Cat, A, Γ` | state, urbanicity, language, religion, caste category, age, gender |
| `z ∈ [0,1]` | latent socioeconomic status (SES) |
| `E, N, O` | education, NCCS class, occupation |
| `c ∈ [0,1]` | capital-base index (from NCCS); `c=1` affluent, `c=0` destitute |
| `h = (h_H,…,h_O)` | HEXACO trait means; `h_i(t)` an expressed state |
| `σ_s ∈ [0,1]` | scarcity state (cash pressure) |
| `λ, α, γ` | loss aversion, value curvature, probability-weighting curvature |
| `β, δ` | present-bias and long-run discount factors (β–δ model) |
| `ρ` | reference point (recent income / mental-account baseline) |
| `B(t)` | available cognitive bandwidth at clock time `t` |
| `ν, a, s` | drift rate, decision boundary, diffusion noise (DDM) |
| `Π` | belief precision (inverse variance) |
| `η` | inflation-elasticity coefficient |
| `σ(·)` | logistic function `σ(x)=1/(1+e^{−x})`; `(x)_+ = max(0,x)`; `clip` = clamp to range |

---

## 1. The persona as a probabilistic graphical model

A persona is a sample `P ∼ 𝒫(·)` from a directed factorization (Bayesian network):

```
𝒫(persona) = P(S)·P(U|S)·P(Λ|S)·P(Rel|S)·P(Cat|Rel)·P(A)·P(Γ)
           · P(z | U,Cat) · δ(E − g_E(z)) · δ(N − g_N(z)) · P(O | z,U,Γ,A)
           · P(Ψ | z,Rel,region) · P(K | N,O,z,A,Ψ) · P(C | O,A,z,region) · P(Π_para | Ψ,K)
```

where Ψ = psyche, K = decision-knobs, C = contextual dynamics, Π_para = paradoxes. The arrows encode the **interlocking dependencies**: demographics → SES latent → education/class/occupation → psychology → decision parameters → context. Deterministic maps are written `δ(·)`; a final **consistency projection** `Φ` (Sec. 2.4) repairs impossible cells.

**Dependency DAG (textual):**
`S → {U, Λ, Rel}`, `Rel → Cat`, `{U,Cat} → z`, `z → {E, N, O, smartphone}`, `{A,Γ,U} → O`, `{z,Rel,region} → Ψ`, `{N,O,z,A,Ψ} → K`, `{O,A,z,region,K} → C`.

---

## 2. Demographic skeleton (conditional distributions)

**2.1 Categorical draws.** State `S ∼ Cat(w)` with `w_s ∝` population share. Then
`U|S ∼ Bernoulli(ρ_S)` (rural prob.), `Λ|S ∼ Cat(π_S)`, `Rel|S ∼ Cat(θ_S)`, `Cat|Rel ∼ Cat(γ)`, `A ∼ Cat(a)`, age `∼ Uniform(band)`, `Γ ∼ Cat([.51,.485,.005])`.

**2.2 Latent SES.** A continuous status variable with structured mean:

```
z = clip01( μ_z + ε ),   ε ∼ N(0, σ_z²),  σ_z = 0.20
μ_z = 0.50 + βU·𝟙[urban] + βC·1{Cat}
βU = +0.12 (urban) / −0.08 (rural);  βC = +0.06 (General), −0.06 (SC/ST), 0 (OBC)
```

**2.3 Deterministic SES maps.** Education and class are **quantile thresholds** of `z`:

```
E = g_E(z):  z<.12 → none; <.35 → some; <.55 → Class10; <.70 → Class12; <.90 → graduate; else postgraduate
N = g_N(z) = NCCS[ ⌊15 z⌋ ]   over the ordered ladder E3<E2<E1<D<D<C2<C2<C1<C1<B2<B2<B1<A3<A2<A1
c = capital index = (rank(N) )/14 ∈ [0,1]
```

**2.4 Occupation + the consistency projection Φ.** Occupation is drawn from an SES- and context-conditioned set, then projected to remove contradictions:

```
O₀ ∼ Cat( occ-pool(z, U, Γ, A) )
Φ:  if E ∈ {graduate, postgraduate} ∧ tier(O₀)=manual  ⟹  O ← pivot to {clerical, teaching, skilled self-employment}
    if tier(O)=corporate ∧ E ∈ {none, some, Class10}   ⟹  E ← graduate
```

`Φ` is idempotent and guarantees `P(graduate ∧ manual-labour)=0` — the structural fix that eliminated the "graduate mason" failure class.

---

## 3. Psyche: traits as density distributions

HEXACO trait **means** are truncated Gaussians; some depend on `z`:

```
h_i ∼ TN(μ_i, τ_i², 0, 1),   μ_O = 0.42 + 0.20 z   (openness rises with SES)
```

Following Fleeson, a trait is a *distribution of states*; the **expressed state** on occasion `t` is re-sampled:

```
h_i(t) ∼ N(μ_i, ς_i²)            (within-person variance ς_i ≫ 0 ⇒ two equal-mean personas still differ)
```

Religiosity `r ∼ TN(μ_r(region), …)`, external locus `ℓ = clip01(0.5 + 0.2 r + ε)`, interdependence `ι`, power-distance `pd`, prior precision `Π ∼ TN(0.62,…)`, reflective disposition `R = clip01(0.25 + 0.50 z)`.

---

## 4. Behavioural-economics core

**4.1 Prospect-theory value function** (Tversky–Kahneman 1992), reference-dependent at `ρ`:

```
v(x) = (x−ρ)^α              if x ≥ ρ
     = −λ · (ρ−x)^α         if x < ρ
```

with curvature `α ≈ 0.88` and **loss aversion as a function of the capital base** (the key scaling law):

```
λ(c) = clip( λ_min + (λ_max − λ_min)(1 − c) + ε_λ ,  1.0, 3.6 )
λ_min = 2.0 (affluent),  λ_max = 3.0 (destitute)
```

So `λ` rises monotonically as wealth falls: B1 (`c≈0.73`) → `≈2.27`, C2 (`c≈0.43`) → `≈2.57`, E3 (`c=0`) → `≈3.0`. (A loss looms up to ~3× a matched gain for the very poor.)

**4.2 Probability weighting** (Prelec): `w(p) = exp(−(−ln p)^γ)`, `γ ≈ 0.65` (overweights rare events).

**4.3 Quasi-hyperbolic (β–δ) discounting** (Laibson):

```
U = u₀ + β · Σ_{k≥1} δ^k u_k
```

with **present-bias decreasing in scarcity**:

```
β(σ_s) = clip( β_max − ψ·σ_s , 0.25, 0.95 ),   β_max=0.95, ψ=0.60
```

Under cash pressure `β→0.35`: the future is steeply discounted, "small cash now ≫ larger sum later."

---

## 5. Scarcity and the cognitive-bandwidth tax

Scarcity (Mullainathan–Shafir) imposes a measurable cognitive load. With scarcity state `σ_s`,

```
ΔIQ(σ_s) = −Δ_max · σ_s ,   Δ_max ≈ 13 points
```

expressed as a normalized bandwidth penalty `D_scar = b_s·σ_s` (`b_s≈0.25`). The **time-of-day risk window** is the interval where bandwidth is minimal *and* the daily target is unmet (Sec. 6), the period of peak susceptibility to predatory offers.

---

## 6. Somatic homeostasis: bandwidth over the day

Available cognitive bandwidth is depleted by physical fatigue, circadian phase, and scarcity:

```
B(t) = clip01( B_max − D_phys(t) − D_circ(t) − D_scar )
B_max = 1
D_phys(t) = δ_p · ((t − t₀)_+)^p              (linear p=1; convex p>1 for aging manual labour)
   aging-manual variant:  D_phys(t) = δ_p · ( e^{ρ_p (t−t₀)_+} − 1 )      (exponential cortisol build-up)
D_circ(t) = A_c · ( 1 − cos( 2π (t − φ)/24 ) ) / 2 ,   φ ≈ 10:00 (alertness peak)
```

`t₀` = shift start. The **peak-exhaustion window** is `t* = argmin_t B(t)` — e.g. mason `≈17–19h`, farmer `≈11–15h` (heat), office `≈16–18h`. Below a threshold `θ_B`, the deliberation gate (Sec. 7) closes and the persona falls to System-1 heuristics.

---

## 7. Dual-process arbitration

The probability of engaging effortful System-2 deliberation is a logistic gate over stakes, time-pressure, bandwidth and disposition:

```
p_S2 = σ( w₀ + w_B(B(t) − θ_B) + w_R·R + w_K·stakes − w_T·time_pressure − w_F·(1−B(t)) )
```

If `Bernoulli(p_S2)=1` → full prospect-theoretic evaluation (Sec. 8). Else → fast heuristic: satisfice to the first option clearing an aspiration level, anchored on the status quo. Stress/fatigue/scarcity all *lower* `p_S2` (push toward habit), as observed.

---

## 8. Choice as drift-diffusion

Given two options, evidence accumulates `dX = ν dt + s dW`, deciding when `|X| ≥ a`. With a value difference `ΔV = U(offer) − U(status quo)` (Sec. 11):

```
ν = κ_ν · ΔV / scale                         (drift ∝ value difference)
X₀ = m · somatic_marker                       (gut "approach/avoid" start-point bias, Damasio)
a = a₀ · ( 1 − ζ·(time_pressure + (1−B(t))) )  (boundary collapses under pressure/fatigue ⇒ faster, noisier)
P(accept) = 1 / ( 1 + exp( −2 ν a / s² ) )     (logistic choice probability)
E[RT] ≈ (a/ν)·tanh(a ν / s²) + t_nd ;   confidence ∝ |ν| a
```

A negative somatic marker (e.g. a past debt memory) shifts `X₀` toward rejection *before* deliberation.

---

## 9. Belief updating and misinformation

Beliefs are precision-weighted (Bayesian / predictive-coding) updates. Prior `(μ_b, Π_b)`, evidence `(e, Π_e)`:

```
μ_b' = (Π_b μ_b + Π_e e)/(Π_b + Π_e) ;   Π_b' = Π_b + Π_e
```

An incoming claim (e.g. a WhatsApp forward) is **adopted** with probability

```
P(accept claim) = σ( κ₁·trust(source) + κ₂·ingroup_align − κ₃·Π_b·|e − μ_b| )
```

High prior precision `Π_b` down-weights discordant evidence ⇒ stubbornness/echo-chambering emerges from one mechanism; identity-aligned, high-trust sources clear the bar easily.

---

## 10. Social diffusion and temporal horizon

**10.1 Bounded-confidence opinion dynamics** (Deffuant). For neighbour `j` with tie weight `τ_ij`:

```
o_i ← o_i + μ·τ_ij·(o_j − o_i) · 𝟙[ |o_i − o_j| < ε_ij ]
```

with the confidence bound `ε_ij` **smaller across caste/religion lines** ⇒ in-group convergence, cross-group hardening.

**10.2 Socioemotional selectivity** (Carstensen). Perceived future time `T(age)` shrinks with age; the **novelty-resistance index**:

```
NRI = clip01( ν₀ + ν₁·𝟙[age≥58] − ν₂·h_O − ν₃·𝟙[educated] + ν₄·𝟙[rural] )
horizon = Expansive (age<30) | Provisioning (30–57) | Constricted (≥58)
```

Elders re-weight communion/legacy utility; youth weight exploration. This multiplies the novelty term in `U(X)`.

---

## 11. The unified decision functional

For a stimulus `X` with attribute changes `Δ_k` (gains/losses vs. account references `ρ_k`) and probabilities `p_k`, the **subjective value** is multi-attribute prospect-weighted, adjusted by social and framing terms:

```
U(X) = Σ_k ω_k · w(p_k) · v(Δ_k − ρ_k ; α, λ(c))         (prospect core, mental accounts ω_k non-fungible)
       + Φ_frame(X)                                       (+ if framed as "shield assets"; − if "aggressive growth")
       − Φ_social(X)                                      (deference penalty if X threatens standing; → −∞ until consulted)
       − Φ_novelty(X)·NRI                                 (penalty for unproven/novel options, scaled by horizon)
```

The acceptance decision is then gated and accumulated:

```
P(accept X | persona, t) =  p_S2 · DDM(ΔV; a, ν, s)  +  (1 − p_S2) · heuristic(X)
ΔV = U(X) − U(status quo)
```

with `λ`, `β`, `B(t)`, `X₀`, `a` all instantiated from the persona's parameters and the clock. **Macro coupling:** under a price shock, `λ_eff = clip(λ(c)·(1 + κ·η), …)` (κ≈0.55), so the same offer is rejected harder in a high-inflation week.

---

## 12. Population calibration and validation

**12.1 Iterative Proportional Fitting (IPF).** Raw draws match marginals only approximately. Given target margins `T_d(·)` (Census/NFHS/PLFS) over dimensions `d`, reweight cells `x`:

```
repeat until convergence:
   for each dimension d, for each margin level m:
       w(x) ← w(x) · T_d(m) / Σ_{x'∈m} w(x')        ∀ x with x_d = m
```

Converges (RAS algorithm) to the maximum-entropy fit consistent with all margins; each persona carries a **representativeness weight** `w(x)`.

**12.2 Prediction-powered inference (PPI)** for validation. With `n` real labels `Y_i` and model outputs `f(X_i)`, the bias-corrected population estimate is

```
θ̂_PPI = θ̂_synthetic − (1/n) Σ_{i=1}^n ( f(X_i) − Y_i )
```

unbiased and tighter than the small-sample estimate regardless of model error — the honest confidence interval the engine ships.

---

## 13. The generation algorithm

```
GENERATE():
  1. Sample skeleton  S,U,Λ,Rel,Cat,A,Γ        (Sec. 2.1)        O(1)
  2. Sample z; map E,N,c; draw O₀; apply Φ      (Sec. 2.2–2.4)
  3. Sample psyche h, r, ℓ, ι, pd, Π, R         (Sec. 3)
  4. Compute decision parameters:
        c→λ(c); σ_s→β(σ_s); ρ from income band;
        somatic (t₀,δ_p,p,φ)→B(·) and t*;        (Sec. 4–8)
        NRI(age,h_O,E,U)                          (Sec. 10.2)
  5. Emit persona = (skeleton, psyche, decision_model, contextual, paradoxes, text projections)
POPULATION(M):  draw M personas; run IPF to targets; attach weights; PPI-validate on holdout.
```

Per-persona cost `O(1)`; population `O(M·I·D)` for `I` IPF sweeps over `D` dimensions. Generation throughput ≈ 1.5×10⁵ personas/min (pure sampling).

---

## 14. Parameter table (defaults)

| Param | Value | Param | Value |
|---|---|---|---|
| `σ_z` (SES noise) | 0.20 | `α` (PT curvature) | 0.88 |
| `λ_min, λ_max` | 2.0, 3.0 | `γ` (Prelec) | 0.65 |
| `β_max, ψ` | 0.95, 0.60 | `δ` (long-run) | 0.97 |
| `Δ_max` (scarcity IQ) | 13 | `b_s` | 0.25 |
| `B_max, θ_B` | 1.0, 0.45 | `φ` (circadian peak) | 10:00 |
| `a₀` (DDM boundary) | 1.0 | `ζ` (boundary collapse) | 0.4 |
| `κ_ν` (drift gain) | 1.2 | `s` (DDM noise) | 0.6 |
| `κ` (macro→λ) | 0.55 | `NRI` base/age/edu | 0.35 / +0.45 / −0.10 |

All constants are tunable and are the **fit targets** when calibrating against real Indian survey microdata.

---

*Reference implementation: `persona_math.py`. Every equation here is a function there; `evaluate_offer(persona, offer, hour)` composes Sections 4–11 into a single acceptance probability.*
