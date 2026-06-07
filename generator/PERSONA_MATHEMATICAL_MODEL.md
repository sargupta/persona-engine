# The Mathematical Model of Persona Generation (v1.1)

This document specifies the persona engine as a **formal probabilistic and computational model**. A persona is a sample from a defined joint distribution; cognitive and behavioural parameters are given by explicit equations grounded in the literature (prospect theory, hyperbolic discounting, scarcity theory, drift-diffusion, predictive coding, socioemotional selectivity).

> **Status (read first).** This is a *structured, falsifiable hypothesis*, not a fitted model. The component equations are canonical and correctly stated; the **constants are not yet estimated from data**, and the model is over-parameterised. §15 (Limitations & Identifiability) is mandatory reading and classifies every parameter by whether it is literature-fixed, estimable, or set by design. v1.1 corrects six issues found in self-review: (1) the decision functional is now **dimensionless and bounded**; (2) parameters are classified by identifiability and the dual-process gate collapsed from 6 weights to 2; (3) the capital index is now a **cardinal log-money** quantity, with λ a *distribution*; (4) doc and code are **reconciled**; (5) the bandwidth function is **bounded and never saturates**; (6) IPF is correctly described as **margins-only**, with a joint-fidelity correction added. The reference implementation is `persona_math.py`.

---

## 0. Notation

| Symbol | Meaning |
|---|---|
| `S,U,Λ,Rel,Cat,A,Γ` | state, urbanicity, language, religion, caste category, age, gender |
| `z ∈ [0,1]` | latent socioeconomic status (SES) |
| `m, c ∈ [0,1]` | monthly-consumption proxy (₹); cardinal **log-money** capital index |
| `h_i, h_i(t)` | HEXACO trait mean; expressed state on occasion `t` |
| `σ_s ∈ [0,1]` | scarcity state | `λ, α, γ` | loss aversion, value curvature, prob-weighting curvature |
| `β, δ, ρ` | present-bias, long-run discount, reference point |
| `L(t), B(t)` | depletion load and available cognitive bandwidth at clock time `t` |
| `μ, a, z0, s` | DDM drift, boundary separation, **start point**, noise |
| `Π, η` | belief precision; inflation-elasticity coefficient |
| `σ(·)` | logistic `1/(1+e^{−x})`; `(x)_+ = max(0,x)`; `clip` = clamp; `Φ_N` = standard-normal CDF |

---

## 1. The persona as a probabilistic graphical model

A persona is a sample `P ∼ 𝒫(·)` from a directed factorisation:

```
𝒫(persona) = P(S)·P(U|S)·P(Λ|S)·P(Rel|S)·P(Cat|Rel)·P(A)·P(Γ)
           · P(z | U,Cat) · 𝟙[E = g_E(z)] · 𝟙[N = g_N(z)] · P(O | z,U,Γ,A)
           · P(Ψ | z,Rel,region) · P(K | N,O,z,A,Ψ) · P(C | O,A,z,region) · P(Π_para | Ψ,K)
```

Deterministic maps use the **Kronecker indicator** `𝟙[·]` (not a Dirac delta — `E,N` are discrete). A final **consistency projection** `Φ` (§2.4) repairs impossible cells. *Caveat:* the DAG is **top-down** (`z → E,N,O`); it does not model the reverse/joint determination of education and occupation, and the structure is hand-specified, not learned (§15).

---

## 2. Demographic skeleton

**2.1 Categorical draws.** `S ∼ Cat(w)`, `U|S ∼ Bernoulli(ρ_S)`, `Λ|S ∼ Cat(π_S)`, `Rel|S ∼ Cat(θ_S)`, `Cat|Rel ∼ Cat(γ)`, `A ∼ Cat(a)`, `Γ ∼ Cat([.51,.485,.005])`.

**2.2 Latent SES.** To avoid Gaussian-clipping point masses, use a **logit-normal** latent:

```
z = σ( ζ ),   ζ ∼ N( μ_ζ , σ_ζ² ),   σ_ζ = 0.9
μ_ζ = logit(0.50) + βU·𝟙[urban] + βC·1{Cat},   βU = ±0.5,  βC ∈ {+0.3,0,−0.3}
```

`z ∈ (0,1)` smoothly, no boundary atoms.

**2.3 SES maps.** `E = g_E(z)` and `N = g_N(z)` are quantile thresholds of `z` (the cut-points are stipulated design choices — Class C, §15).

**2.4 Cardinal capital index (corrected).** Replace the ordinal `rank(N)/14` with a **log-money** index, since the utility of money is approximately logarithmic. Let `m = MPCE(N)` be a median monthly-consumption proxy per class:

```
c = clip(  ( ln m − ln m_min ) / ( ln m_max − ln m_min ) ,  0, 1 ),   m_min=4000, m_max=120000 (₹)
```

`c` is now cardinal and interpretable, not an equal-spacing assumption on ordinal labels.

**2.5 Occupation + consistency projection Φ.**

```
O₀ ∼ Cat( occ-pool(z,U,Γ,A) )
Φ:  E ∈ {grad,PG} ∧ tier(O₀)=manual  ⟹  O ← pivot{clerical, teaching, skilled self-employment}
    tier(O)=corporate ∧ E ∈ {none,some,Class10} ⟹ E ← graduate
```

`Φ` is idempotent ⇒ `P(graduate ∧ manual-labour)=0`.

---

## 3. Psyche: traits as density distributions

Trait **means** are sampled with an explicit correlation structure (so the Schwartz/HEXACO coherence is not thrown away):

```
h ∼ TN( μ(z,region), Σ_h ),   Σ_h ≠ diagonal   (e.g. H–A positive, O–Conscientiousness mild)
μ_O = clip( 0.42 + 0.20 z )    (openness rises with SES; coefficient = Class B/C)
```

Following Fleeson, the **expressed state** on occasion `t` is re-sampled `h_i(t) ∼ N(h_i, ς_i²)` — so two equal-mean personas still diverge, and behaviour ≠ trait.

---

## 4. Behavioural-economics core

**4.1 Prospect value** (Tversky–Kahneman 1992), reference-dependent at `ρ`, evaluated on **money normalised by the reference** so it is dimensionless:

```
ṽ(x) = ( (x−ρ)/ρ )^α                if x ≥ ρ
     = −λ · ( (ρ−x)/ρ )^α           if x < ρ
α ≈ 0.88  (Class A, literature-fixed)
```

**Loss aversion as a distribution over the capital base** (not a deterministic law):

```
λ ∼ Normal( λ̄(c), s_λ² ),   λ̄(c) = λ_min + (λ_max−λ_min)(1−c),   λ_min=2.0, λ_max=3.0, s_λ=0.15
```

The earlier per-class "band table" is exactly the set of quantiles of this distribution. Note `λ̄` is a *modelling choice* on the cardinal `c`; the literature does not establish it as a law (§15).

**4.2 Probability weighting** (single-parameter Prelec): `w(p)=exp(−(−ln p)^γ)`, `γ≈0.61` (Class A).

**4.3 Quasi-hyperbolic (β–δ) discounting** (Laibson), **used** in the multi-period evaluation (§11):

```
U_intertemporal = u₀ + β·Σ_{k≥1} δ^k u_k,   β(σ_s)=clip(β_max − ψ σ_s, .25, .95),  δ=0.97/yr
```

For one-shot offers the future benefit enters as `β·w(p)·ṽ(gain)` (single discounted term); δ governs multi-period streams only.

---

## 5. Scarcity → deliberation capacity (corrected wiring)

The Mani et al. finding (~13 IQ-pt pre/post-harvest swing) is **converted explicitly** into a bandwidth penalty rather than left as flavour. Normalising IQ by a working-memory span of ~`Q=40` points:

```
D_scar(σ_s) = (Δ_max / Q) · σ_s ,   Δ_max ≈ 13   ⇒  D_scar ∈ [0, 0.33]
```

`D_scar` enters the bandwidth load `L(t)` (§6) and thus the deliberation gate (§7). (Caveat: the 13-pt figure is two-state, not a calibrated continuum — §15.)

---

## 6. Somatic homeostasis: bounded bandwidth (corrected)

Cognitive bandwidth is now a **strictly positive, bounded, multiplicative** function of total depletion load `L(t)` — it never saturates at 0, preserving resolution in the evening fatigue regime. Physical exertion accrues **only during the shift window** `[t₀, t_end]` and then **recovers** at rate `ρ_rec` once work stops; without this windowing a monotone `D_phys` would push the argmin trivially to the last waking hour for *every* occupation, erasing trade structure:

```
L(t)     = D_phys(t) + D_circ(t) + D_scar
work(t)  = ( min(t, t_end) − t₀ )_+                         (exertion accrued, frozen after shift)
D_phys(t)= ( δ_p·work(t) − ρ_rec·(t−t_end)_+ )_+            (linear; aging-manual: δ_p·(e^{ρ_p·work}−1))
D_circ(t)= A_c·(1 − cos(2π(t−φ)/24))/2,   φ ≈ 10:00
B(t)     = B_max · exp( −L(t) )  ∈ (0, B_max]
```

The shift window `[t₀, t_end]` is set per occupation (farmer 05–13, mason 08–18, vendor 07–21, driver 08–17, domestic 06–14, white-collar 09–18; Class C). The **peak-exhaustion hour is then computed, not looked up**: `t* = argmin_t B(t) = argmax_t L(t)` over the waking grid. This *emergently* reproduces the trade-specific peaks (farmer→13:00, mason→18:00, vendor→21:00, driver→17:00) that the v1.0 generator had hard-coded — so the lookup table is replaced by a mechanism, and **doc and code now compute the identical `argmin`** (the §4-drift reconciliation).

---

## 7. Dual-process arbitration (collapsed to 2 free parameters)

A single linear **deliberation drive** `d`, then a 2-parameter logistic gate (the six ad-hoc weights are replaced by fixed design priors inside `d`, leaving only a slope and threshold to estimate):

```
d = κ_K·stakes + κ_R·R − κ_T·time_pressure − κ_F·(1−B(t))     (design priors κ_•, Class C)
p_S2 = σ( s_g · ( d − θ_g ) )                                 (free: slope s_g, threshold θ_g — Class B)
```

`Bernoulli(p_S2)=1` ⇒ System-2 (full evaluation, §8/§11); else System-1 (satisfice on the status quo).

---

## 8. Choice as drift-diffusion, with a **start-point** somatic bias (corrected)

Evidence `dX = μ dt + s dW` accumulates between absorbing boundaries `{0, a}`, starting at `z0`. The **somatic marker biases the start point** (a prior, not the evidence rate), and we use the **correct general two-boundary hitting probability** (Cox–Miller):

```
z0 = a · clip( 0.5 + b_m·marker , 0.05, 0.95 )     (marker<0 ⇒ z0<a/2 ⇒ avoid-prior)
μ  = κ_ν · U                                        (drift ∝ the bounded value U, §11)
P(accept) = ( e^{−2μ z0/s²} − 1 ) / ( e^{−2μ a/s²} − 1 ),   μ ≠ 0
          = z0 / a,                                  μ = 0
E[T_dec] = (z0/μ) − (a/μ)·( 1 − e^{−2μ z0/s²} )/( 1 − e^{−2μ a/s²} ) ;   confidence ∝ |μ|·a
```

With `z0=a/2` this reduces to `1/(1+e^{−μa/s²})`. A past-debt memory (`marker<0`) lowers acceptance *before* deliberation.

---

## 9. Belief updating and misinformation

Conjugate precision-weighted (predictive-coding) update; prior `(μ_b,Π_b)`, evidence `(e,Π_e)`:

```
μ_b' = (Π_b μ_b + Π_e e)/(Π_b+Π_e);   Π_b' = Π_b + Π_e
P(accept claim) = σ( κ₁·trust + κ₂·ingroup − κ₃·Π_b·|e−μ_b| )
```

High prior precision down-weights discordant evidence ⇒ stubbornness/echo-chambering from one mechanism.

---

## 10. Social diffusion and temporal horizon

**Bounded-confidence (Deffuant):** `o_i ← o_i + μ·τ_ij·(o_j−o_i)·𝟙[|o_i−o_j|<ε_ij]`, with `ε_ij` smaller across caste/religion lines.

**Socioemotional selectivity (Carstensen):**
```
NRI = clip01( ν₀ + ν₁·𝟙[age≥58] − ν₂·h_O − ν₃·𝟙[educated] + ν₄·𝟙[rural] )
horizon = Expansive (age<30) | Provisioning (30–57) | Constricted (≥58)
```

---

## 11. The unified decision functional (dimensionless & bounded — corrected)

Every component is squashed onto a common `[−1,1]` scale, then combined with **non-negative weights that sum to 1**, so `U ∈ [−1,1]` and `P(accept)` has interpretable *levels*, not arbitrary ones:

```
g_econ  = tanh( β·w(p)·ṽ(gain) + ṽ(loss) )          (∈ (−1,1); ṽ already money/ρ-normalised, λ_eff used)
g_frame = +1 (shield) | −1 (growth) | 0
g_novel = − NRI · novelty                            (∈ [−1,0])
U = θ_e·g_econ + θ_f·g_frame + θ_n·g_novel ,   θ_e+θ_f+θ_n = 1,   U ∈ [−1,1]
μ = κ_ν·U  →  P(accept) via §8 (start-point DDM)
SOCIAL DEFERENCE GATE (multiplicative, replaces the −∞ penalty):
   if X threatens standing:  P(accept) ← g_consult · P(accept),   g_consult ≈ 0.05
                              (≈0 until an offline consultation flips g_consult→1)
MACRO COUPLING:  λ_eff = clip( λ·(1 + κ·η) , 1, 3.6 )   enters ṽ(loss);  κ≈0.55
```

`θ = (θ_e,θ_f,θ_n)` are the **only** free combination weights (Class C, design priors, e.g. `(0.6,0.2,0.2)`).

---

## 12. Population calibration & validation (corrected)

**12.1 IPF fits MARGINS ONLY.** Given target margins `T_d` (Census/NFHS/PLFS), RAS reweighting:
```
repeat: for each dimension d, level m:  w(x) ← w(x)·T_d(m)/Σ_{x':x'_d=m} w(x')
```
converges to the **maximum-entropy** fit *consistent with the specified margins* — it does **not** reproduce higher-order joint structure beyond what the margins imply. This is a real limitation given the project's joint-distribution thesis.

**12.2 Joint-fidelity correction (added).** To inject real pairwise+ dependence, follow IPF with one of:
(i) a **Gaussian/vine copula** fit to the standardised attribute correlations from microdata, resampling the dependence while preserving the IPF margins; or (ii) **Gibbs resampling** over empirical conditional tables `P(x_d | x_{−d})`; or (iii) a conditional deep-generative model. The engine's design (z → conditionals) is a step toward (ii).

**12.3 Prediction-powered inference (corrected rectifier).** With `n` labelled `(X_i,Y_i)∼target` and `N≫n` unlabelled with predictions `f`:
```
θ̂_PPI = (1/N) Σ_{j≤N} f(X_j)  +  (1/n) Σ_{i≤n} ( Y_i − f(X_i) )
```
unbiased *iff* the labelled set is i.i.d. from the target population (still the expensive ingredient).

---

## 13. The generation algorithm

```
GENERATE():
  1. skeleton S,U,Λ,Rel,Cat,A,Γ                       O(1)
  2. z (logit-normal); E,N,c (log-money); O₀; apply Φ
  3. psyche h~TN(μ,Σ_h), states, r, ℓ, ι, pd, Π, R
  4. decision params:  λ∼N(λ̄(c),s_λ); β(σ_s); ρ=MPCE; B(·),t*=argmin; NRI(age,h_O,E,U)
  5. emit persona (+ decision_model, contextual, paradoxes, text projections)
POPULATION(M): draw M; IPF to margins; joint-fidelity correction (§12.2); PPI-validate.
```

Per-persona `O(1)`; population `O(M·I·D)` for `I` IPF sweeps; ≈1.5×10⁵ personas/min (pure sampling).

---

## 14. Parameter table & identifiability classes

| Param | Value | **Class** |
|---|---|---|
| `α` (PT curvature) | 0.88 | **A** literature-fixed |
| `γ` (Prelec) | 0.61 | **A** |
| `δ` (annual discount) | 0.97 | **A** |
| `Δ_max` (scarcity IQ) | 13 | **A** |
| `φ` (circadian peak) | 10:00 | **A** |
| `λ_min, λ_max, s_λ` | 2.0, 3.0, 0.15 | **B** estimable |
| `ψ` (present-bias slope) | 0.60 | **B** |
| `κ_ν` (drift gain), `a`, `s` | 1.2, 1.0, 0.6 | **B** |
| `s_g, θ_g` (gate) | — | **B** |
| `κ_K,κ_R,κ_T,κ_F` (gate drive) | design | **C** fixed by fiat |
| `θ_e,θ_f,θ_n` (U weights) | 0.6,0.2,0.2 | **C** |
| `δ_p, ρ_rec` (exertion/recovery) | 0.04–0.08, 0.10 | **C** |
| `[t₀,t_end]` (shift window) | per-occupation | **C** |
| `b_m, b_s, ε_ij` | design | **C** |

**Class A** = fixed from published estimates. **Class B** = estimable from a modest labelled choice set (hundreds–thousands of decisions). **Class C** = structurally non-identifiable from choice data alone ⇒ set by design and held fixed (not pretended to be fittable).

---

## 15. Limitations & honest caveats

1. **Not a fitted model.** No constant has been estimated from real Indian behavioural data. The model **predicts nothing that has been empirically verified**; it is a falsifiable hypothesis awaiting calibration. Any quantitative output should be read as illustrative, not as a forecast.
2. **Over-parameterised; many parameters non-identifiable.** Even after collapsing the gate to two parameters, several constants (Class C) cannot be recovered from choice data and are *fixed by design*. The §14 classes make this explicit rather than hiding it.
3. **`λ̄(c)` is a modelling choice, not a law.** Loss aversion's status as a stable constant is itself disputed (Gal & Rucker 2018); the linear-in-log-money form is a plausible prior, presented as `λ ∼ Normal(λ̄(c), s_λ²)` with explicit uncertainty.
4. **`U` levels are interpretable but uncalibrated.** Making `U` dimensionless (§11) fixes the *incoherence* of v1.0, but the *mapping* from `U` to real acceptance rates still requires calibration of `κ_ν, a, s` against observed choices.
5. **IPF fits margins, not joints.** §12.1 is honest about this; real joint fidelity needs the §12.2 correction, which itself requires microdata.
6. **Structural simplifications.** The DAG is top-down (no reverse education↔occupation causality); the two-process fatigue/alertness interaction is approximated additively-in-the-exponent; trait correlations `Σ_h` are stipulated, not estimated; the social/diffusion layer is single-shot here.
7. **Sensitive attributes stay outside the validity envelope** (caste/religion/communal) until specifically validated, regardless of how the equations behave.

The honest one-line summary: **correct canonical building blocks, a coherent (now dimensionally consistent) architecture, and a transparent ledger of what is fixed, estimable, or stipulated — but an uncalibrated hypothesis, not an empirically supported predictor, until the Class-B parameters are fit and the population is validated by PPI on real data.**

*Reference implementation: `persona_math.py` (every equation a function; `evaluate_offer` composes §4–§11).*
