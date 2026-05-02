# Stats Engine — Key Design Decisions

Why each non-obvious technical choice was made in `backend/app/stats/`.
Each section gives the decision, the alternatives considered, and the reasoning.

---

## Why OLS for the CUPED Theta Coefficient?

**The decision:** `cuped._estimate_theta` computes θ = Cov(X, Y) / Var(X) — the ordinary least-squares slope from a pooled linear regression of the experiment-period outcome (Y) on the pre-experiment covariate (X).

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Ridge regression | Introduces L2 shrinkage bias — θ is pulled toward zero, which *reduces* CUPED's variance reduction below its theoretical maximum. No regularization is needed when N is large (which it always is when CUPED is beneficial). |
| LASSO / ElasticNet | Adds a hyperparameter (λ) that must be tuned, and can zero out the covariate entirely for a bad choice of λ. Unnecessary complexity for a single covariate. |
| ML models (gradient boosting, neural nets) | Can capture nonlinear pre-post relationships, but they overfit on the pre-period and introduce bias — the adjustment is no longer constant across groups, violating the unbiasedness argument. The OLS guarantee that E[Y_adj_t] − E[Y_adj_c] = E[Y_t] − E[Y_c] holds only for linear adjustments with population-level θ. |
| Per-group OLS (separate θ_c, θ_t) | Introduces bias because θ is estimated post-randomization; the adjustment changes asymmetrically across groups. Pooled OLS is the correct estimator per the Deng et al. (2013) paper that introduced CUPED. |

**Why OLS is correct:**
The CUPED guarantee — that subtracting θ·(X_i − X̄) does not change the expected treatment effect — requires θ to be estimated on the full pooled population *before* looking at group membership. OLS minimizes E[(Y − θX)²] in the population, producing the unique linear coefficient that maximally reduces variance without bias. The closed-form solution is O(n) to compute, numerically stable, and has no hyperparameters. Any more complex estimator would require cross-validation and risk data leakage through group-specific fitting.

---

## Why O'Brien-Fleming Over Pocock Boundaries?

**The decision:** `sequential.py` implements O'Brien-Fleming (OBF) alpha-spending boundaries rather than Pocock's constant boundary.

**The core difference:**

| Property | O'Brien-Fleming | Pocock |
|---|---|---|
| Boundary shape | Decreasing with information (strict early, lenient late) | Constant across all looks |
| Final-look threshold (K=5, α=0.05) | z* ≈ 1.99 | z* ≈ 2.41 |
| Power cost vs fixed-horizon | ~0.5% | ~5–8% |
| Most conservative look | First (z* ≈ 4.56 at t=0.1) | All equal |

**Why OBF:**

1. **Most experiments do not stop early.** Pocock's constant boundary penalizes the *final* look regardless of whether an interim look was ever used. An experiment that runs to its planned N with K=5 interim looks has a Pocock final-look threshold of z=2.41 vs. OBF's z≈1.99 — nearly the same as the standard 1.96. Pocock permanently inflates the final look cost even if no interim was triggered.

2. **OBF is conservative exactly where it should be.** At 10% of planned information, the data is too sparse to trust. OBF sets z*≈6.2 at t=0.1, making accidental early stops essentially impossible. Pocock would stop at z=2.41 — the same bar as at full information — which overweights noisy early data.

3. **Power is nearly preserved at the final look.** Because OBF spends almost no alpha early (the spending function is nearly flat near t=0), the final-look boundary is close to the unadjusted 1.96. Teams that use sequential testing only for safety stops (not planning to stop early) lose almost nothing in power.

4. **Intuitive: OBF says "extraordinary evidence to stop early, ordinary evidence at the end."** Pocock says "the same extraordinary bar at every look including the final one," which analysts find confusing and which penalizes experiments that ran correctly to completion.

**When Pocock would be preferred:** If you *expect* to stop early in most experiments and the extra stringency at the final look is an acceptable cost — for example, in clinical trials designed specifically for adaptive stopping. Product A/B testing rarely meets this criterion.

---

## Why Benjamini-Hochberg Over Bonferroni as the Default for Multiple Comparisons?

**The decision:** `corrections.py` offers Bonferroni, Holm-Bonferroni, and Benjamini-Hochberg (BH), but `engine.py` defaults to BH when multiple metrics are present.

**The competing options:**

| Method | Controls | Power | Assumption |
|---|---|---|---|
| Bonferroni | FWER | Lowest | None |
| Holm-Bonferroni | FWER | Better than Bonferroni | None |
| Benjamini-Hochberg | FDR | Highest | Positive metric dependence (PRDS) |

**Why BH is the right default for product A/B testing:**

1. **FDR control is the right goal for iterative product decisions.** FWER control asks: "what is the probability we make *any* mistake across all tests?" This is appropriate when a single false positive has severe consequences (e.g. a drug trial). In product experimentation, the cost of missing a real effect (false negative) is as high as, or higher than, the cost of a false positive that gets caught in follow-up testing. Controlling FDR at 5% means ≤5% of declared winners are false — an acceptable and well-understood rate.

2. **Experiment metrics are almost always positively correlated.** BH is guaranteed to control FDR at α when test statistics satisfy Positive Regression Dependency on Subsets (PRDS). In practice, A/B metrics like conversion rate, revenue per user, session length, and engagement all tend to move together when a treatment works — a strong treatment makes everything better, a weak treatment moves nothing. This positive dependence satisfies PRDS.

3. **Bonferroni is uniformly dominated by Holm.** For FWER control, Bonferroni should never be the default — Holm makes at least as many rejections with an identical FWER guarantee. Bonferroni is kept in the API as a reference and for teams that need its simple closed form, but Holm is the better FWER method.

4. **Power difference is large at typical metric counts.** For m=10 metrics at α=0.05, Bonferroni's threshold is 0.005 across the board. BH's threshold for the top-ranked metric is 0.050; for the second-ranked it is 0.040; and so on. In expectation this is 3–5× more permissive than Bonferroni for metrics that are genuinely significant, meaning BH detects real effects that Bonferroni misses entirely.

5. **Holm is surfaced for confirmatory use cases.** When a team has designated 1–3 pre-specified primary metrics for a confirmatory decision (e.g. "we will only ship if primary_conversion is significant"), Holm is the correct choice: it controls FWER, is uniformly more powerful than Bonferroni, and the consequences of a false positive on a primary metric are high. BH defaults remain for the secondary and guardrail metrics even in that case.

**The practical outcome:** A typical Axiom experiment with 5 metrics — 1 primary, 2 secondary, 2 guardrails — applies BH across all five, but the analyst is prompted to confirm primary-metric significance independently before shipping. This gives the best of both worlds: high power on secondary metrics, with an explicit human gate on the primary.
