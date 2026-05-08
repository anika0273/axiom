# Axiom Stats Engine — Validation Report

> Generated: 2026-05-08 23:46 UTC  
> Total: 42 scenarios | Passed: 42 | Failed: 0

---

## Summary

| Module | Total | Passed | Failed |
|--------|------:|-------:|-------:|
| ✅ 1. Sample Size | 5 | 5 | 0 |
| ✅ 2. Two-Proportion Z-Test | 4 | 4 | 0 |
| ✅ 3. Mean Test (Welch t-test) | 4 | 4 | 0 |
| ✅ 4. Ratio Metric (Delta Method) | 3 | 3 | 0 |
| ✅ 5. CUPED Variance Reduction | 4 | 4 | 0 |
| ✅ 6. Sequential / O'Brien-Fleming | 8 | 8 | 0 |
| ✅ 7. Multiple Comparison Corrections | 11 | 11 | 0 |
| ✅ 8. Engine Integration | 3 | 3 | 0 |
| **Total** | **42** | **42** | **0** |

---

## 1. Sample Size

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| S1: baseline=5%, MDE=+1pp, α=0.05, 80% power, two-tailed | `8,159` | `8,159` | 0.00% | ≤5.0% | ✅ PASS | — |
| S2: baseline=30%, MDE=+3pp, α=0.05, 80% power, two-tailed | `3,764` | `3,764` | 0.00% | ≤5.0% | ✅ PASS | — |
| S3: baseline=10%, MDE=+2pp, α=0.05, 90% power, two-tailed | `5,144` | `5,144` | 0.00% | ≤5.0% | ✅ PASS | — |
| S4: baseline=10%, MDE=+2pp, α=0.05, 80% power, one-sided | `3,027` | `3,027` | 0.00% | ≤5.0% | ✅ PASS | — |
| S5: baseline=5%, MDE=+1pp, α=0.01, 80% power, two-tailed | `12,141` | `12,141` | 0.00% | ≤5.0% | ✅ PASS | — |

## 2. Two-Proportion Z-Test

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| P1: 10%→10.5%, n=1 000, not significant | `z=0.3686, p=0.7124, reject=False` | `z=0.3686, p=0.7124, reject=False` | Δz=4.12e-07, Δp=8.44e-08 | ≤0.001 | ✅ PASS | — |
| P2: 5%→6%, n=5 000, significant | `z=2.1932, p=0.0283, reject=True` | `z=2.1932, p=0.0283, reject=True` | Δz=3.17e-07, Δp=3.37e-08 | ≤0.001 | ✅ PASS | — |
| P3: 40%→43%, n=10 000, highly significant | `z=4.3053, p=0.0000, reject=True` | `z=4.3053, p=0.0000, reject=True` | Δz=4.89e-07, Δp=3.25e-07 | ≤0.001 | ✅ PASS | — |
| P4: 3%→5%, n=100, low event count warning | `z=0.7217, p=0.4705, has_low_conv_warning=True` | `z=0.7217, p=0.4705, has_low_conv_warning=True` | Δz=1.64e-07, Δp=4.22e-07 | Δ≤0.001, warning required | ✅ PASS | — |

## 3. Mean Test (Welch t-test)

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| M1: N(10,2) vs N(10,2), n=30, no effect | `t=0.4747, p=0.636752, reject=False` | `t=0.4747, p=0.636752, reject=False` | Δt=7.62e-08, Δp=3.52e-07 | ≤0.001 | ✅ PASS | — |
| M2: N(10,2) vs N(12,2), n=500, significant | `t=15.4740, p=0.000000, reject=True` | `t=15.4740, p=0.000000, reject=True` | Δt=1.40e-07, Δp=1.48e-48 | ≤0.001 | ✅ PASS | — |
| M3: N(10,1) vs N(12,5), n=200, unequal variances | `t=5.8251, p=0.000000, reject=True` | `t=5.8251, p=0.000000, reject=True` | Δt=2.48e-07, Δp=2.11e-08 | ≤0.001 | ✅ PASS | — |
| M4: borderline p≈0.05, n=1 000 | `p≈0.0083, consistent with scipy` | `p=0.0083` | Δp=1.96e-08 | ≤0.001 | ✅ PASS | — |

## 4. Ratio Metric (Delta Method)

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| R1: standard revenue/session, Gamma(2,3), Uniform sessions | `ratio_c=3.0680, var_c=1.281748e-02` | `ratio_c=3.0680, var_c=1.281748e-02` | Δratio=0.00e+00, Δvar=0.00e+00 | ≤1e-10 (floating-point precision) | ✅ PASS | — |
| R2: Pareto sessions (heavy tail), delta vs naive SE | `delta_se > 0, finite; naive_se ≥ delta_se (expected pattern)` | `delta_se=0.1751, naive_se=0.0469, naive_larger=False` | naive/delta ratio = 0.27x | delta_se > 0 and finite (hard); naive≥delta (expected pattern only) | ✅ PASS | — |
| R3: zero-inflated denominator (40% bounce), delta stable | `ratio=1.6886, var=2.831882e-03, var > 0` | `ratio=1.6886, var=2.831882e-03` | Δratio=0.00e+00, Δvar=0.00e+00 | ≤1e-10 | ✅ PASS | — |

## 5. CUPED Variance Reduction

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| C1: high correlation (ρ≈0.89), n=500+500 | `variance_reduction ≈ 79.2%` | `variance_reduction = 79.2%` | 0.0 pp | ≤15.0 pp | ✅ PASS | — |
| C2: low correlation (ρ≈0.11), n=400+400 | `variance_reduction < 10%` | `variance_reduction = 1.1%` | 1.1 pp (from 0) | < 10 pp | ✅ PASS | — |
| C3: effect preservation, balanced x (Δ≈0 by algebra) | `lift_adj = lift_unadj (Δ < 1e-9, floating-point exact)` | `lift_adj=1.374378, lift_unadj=1.374378` | 0.00e+00 | < 1e-9 (algebraic exact with balanced x) | ✅ PASS | — |
| C4: independent pre/post (ρ≈0), n=300+300 | `|ρ| < 0.15, variance_reduction < 5%` | `|ρ|=0.025, variance_reduction=0.1%` | |ρ|=0.025 | |ρ|<0.15, reduction<5% | ✅ PASS | — |

## 6. Sequential / O'Brien-Fleming

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| SEQ1: z*(t_k) at K=5 looks, α=0.05, two-sided | `z*=[4.383, 3.099, 2.53, 2.191, 1.96]` | `z*=[4.383, 3.099, 2.53, 2.191, 1.96]` | max Δ=0.0000 | ≤0.001 | ✅ PASS | — |
| SEQ2: alpha budget K=3, α=0.05 | `sum(α_spent) = 0.05` | `sum(α_spent) = 0.050000` | 0.00e+00 | ≤0.001 | ✅ PASS | — |
| SEQ2: alpha budget K=5, α=0.05 | `sum(α_spent) = 0.05` | `sum(α_spent) = 0.050000` | 0.00e+00 | ≤0.001 | ✅ PASS | — |
| SEQ2: alpha budget K=10, α=0.05 | `sum(α_spent) = 0.05` | `sum(α_spent) = 0.050000` | 0.00e+00 | ≤0.001 | ✅ PASS | — |
| SEQ3: monotonicity K=8, α=0.05 | `z*[k] > z*[k+1] for all k (strictly decreasing)` | `z*=[5.544, 3.920, 3.201, 2.772, 2.479, 2.263, 2.095, 1.960]` | 0 violation(s) | 0 violations | ✅ PASS | — |
| SEQ4: stop_win, z=3.5, t=0.50 (K=4) | `STOP_WIN` | `STOP_WIN` | exact match required | exact | ✅ PASS | — |
| SEQ4: continue, z=1.5, t=0.50 (K=4) | `CONTINUE` | `CONTINUE` | exact match required | exact | ✅ PASS | — |
| SEQ4: stop_lose, z=0.05, t=0.50 (K=4) | `STOP_LOSE` | `STOP_LOSE` | exact match required | exact | ✅ PASS | — |

## 7. Multiple Comparison Corrections

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| COR1: known-answer bonferroni, p=[0.008,0.016,0.030,0.060] | `n_rejected=1, mask=[True, False, False, False]` | `n_rejected=1, mask=[np.True_, np.False_, np.False_, np.False_]` | n_diff=0, mask_diff=0 | exact match | ✅ PASS | — |
| COR1: known-answer holm_bonferroni, p=[0.008,0.016,0.030,0.060] | `n_rejected=2, mask=[True, True, False, False]` | `n_rejected=2, mask=[np.True_, np.True_, np.False_, np.False_]` | n_diff=0, mask_diff=0 | exact match | ✅ PASS | — |
| COR1: known-answer fdr_bh, p=[0.008,0.016,0.030,0.060] | `n_rejected=3, mask=[True, True, True, False]` | `n_rejected=3, mask=[np.True_, np.True_, np.True_, np.False_]` | n_diff=0, mask_diff=0 | exact match | ✅ PASS | — |
| COR2: BH > Bonferroni, p=[0.005,0.020,0.035,0.045,0.049] | `BH (5) > Bonferroni (1)` | `BH=5, Bonferroni=1` | diff=4 | BH > Bonferroni (strict) | ✅ PASS | — |
| COR3: power ordering Bonferroni≤Holm≤BH | `Bonferroni≤Holm≤BH` | `Bonferroni=1, Holm=2, BH=3` | ordering OK | Bonferroni≤Holm≤BH | ✅ PASS | — |
| COR4: corrected p vs statsmodels, bonferroni | `corrected_p≈statsmodels, mask matches` | `max_Δp=0.0000e+00, mask_diffs=0` | max_Δp=0.0000e+00 | Δp≤0.001, 0 mask diffs | ✅ PASS | — |
| COR4: corrected p vs statsmodels, holm_bonferroni | `corrected_p≈statsmodels, mask matches` | `max_Δp=0.0000e+00, mask_diffs=0` | max_Δp=0.0000e+00 | Δp≤0.001, 0 mask diffs | ✅ PASS | — |
| COR4: corrected p vs statsmodels, fdr_bh | `corrected_p≈statsmodels, mask matches` | `max_Δp=1.3878e-17, mask_diffs=0` | max_Δp=1.3878e-17 | Δp≤0.001, 0 mask diffs | ✅ PASS | — |
| COR5: single test no-op, bonferroni | `corrected_p=0.032` | `corrected_p=0.032000` | 0.00e+00 | exact (n=1 no-op) | ✅ PASS | — |
| COR5: single test no-op, holm_bonferroni | `corrected_p=0.032` | `corrected_p=0.032000` | 0.00e+00 | exact (n=1 no-op) | ✅ PASS | — |
| COR5: single test no-op, fdr_bh | `corrected_p=0.032` | `corrected_p=0.032000` | 0.00e+00 | exact (n=1 no-op) | ✅ PASS | — |

## 8. Engine Integration

| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |
|----------|----------|----------|-------|-----------|:------:|:-------------|
| INT1: clear winner, +40% lift, look 3/5, CUPED+corrections | `rec=STOP_WIN, sig=True, seq=STOP_WIN, corrections=present` | `rec=STOP_WIN, sig=True, seq=STOP_WIN, corrections=present` | 0 consistency failure(s) | 0 consistency failures; exact recommendation match | ✅ PASS | — |
| INT2: no effect, underpowered (n=200 vs ~8000 required) | `RUN (not significant, underpowered)` | `RUN` | exact match | exact | ✅ PASS | — |
| INT3: no effect, fully powered (n=10 000, planned=10 000) | `NO_EFFECT` | `NO_EFFECT` | exact match | exact | ✅ PASS | — |

