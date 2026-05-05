# ML Engine — Method Explainers

## Heterogeneous Treatment Effects (HTE)

**What problem it solves:** Identifies which user segments respond best (or worst) to a treatment, so you can target the rollout instead of shipping to everyone.

**How it works:** An XGBoost model is trained on user features plus "treatment × feature" interaction columns; the treatment effect for each user is then estimated by predicting their outcome under treatment and subtracting their predicted outcome under control. SHAP values on the interaction columns rank which features most change the treatment's impact.

**When NOT to use it:** When the experiment was not truly randomised — interaction effects on observational data are confounded by selection bias, not causal.

**What it assumes about your data:** Users are randomly assigned to control/treatment, all relevant features are numeric or pre-encoded, and each group has at least ten subjects.

**Interview Q&A:**
> *How does XGBoost with interaction terms differ from a causal forest for HTE estimation?*
>
> Both estimate conditional average treatment effects (CATE) but differ in how they model heterogeneity. A causal forest builds trees that directly minimise heterogeneity in treatment response via honest splitting (separate subsamples for building and estimating). XGBoost with interaction terms instead learns a shared representation of features and then uses treatment × feature columns so the model can capture how each feature modifies the treatment effect. Causal forests are theoretically superior for causal inference under minimal assumptions, but XGBoost is faster, benefits from the full ML ecosystem (SHAP, hyperparameter tuning), and in practice performs comparably on large balanced A/B datasets where randomisation already handles confounding.

---

## SHAP for Treatment Effect Attribution

**What problem it solves:** Explains which features are *driving* the HTE — i.e., whether it is device type, purchase history, or account age that determines whether a user benefits from the treatment.

**How it works:** After XGBoost is fitted, a TreeExplainer decomposes each prediction into per-feature SHAP contributions via Shapley values from game theory. Only the interaction columns (`feature_x_treat`) are examined; their mean absolute SHAP across all users is the "treatment modifier importance" ranking.

**When NOT to use it:** When you need a global ATE, not feature-level attribution — SHAP adds overhead and complexity that is unnecessary if you only care about the average result.

**What it assumes about your data:** The XGBoost model is already fitted; SHAP values are only as valid as the model they explain, so model quality matters.

**Interview Q&A:**
> *Why do you compute SHAP values only on the interaction columns rather than all columns?*
>
> Standard SHAP values measure each feature's contribution to the predicted *outcome*, but we want to measure each feature's contribution to the *treatment effect*. The interaction columns (`feature × treatment`) capture exactly the component of the prediction that depends jointly on both the feature and whether the user is treated. Computing mean |SHAP| on those columns isolates treatment-modifier importance from the baseline feature importance, avoiding false positives where a feature predicts the outcome strongly but does not actually moderate how the treatment works.

---

## KMeans Segment Discovery

**What problem it solves:** Finds natural user clusters without specifying them upfront, then profiles each cluster's response to the treatment so you know whether to roll out, hold back, or investigate further per segment.

**How it works:** Features are standardised (z-scored) and KMeans is run for k = 2 to 8; the k that maximises the silhouette score is selected. Each cluster is then profiled by running a statistical significance test (z-test or t-test) on treatment vs control outcomes within that segment.

**When NOT to use it:** When segments have non-convex or highly irregular shapes — KMeans assumes roughly spherical, equal-variance clusters, so it will misclassify ring-shaped or banana-shaped natural groups.

**What it assumes about your data:** All features are numeric and carry roughly comparable scales after standardisation; clusters are approximately convex in the feature space.

**Interview Q&A:**
> *How do you handle the fact that KMeans results are not deterministic?*
>
> We run five independent KMeans refits with different seeds and match clusters across runs by nearest-centroid distance. The variance of per-segment lift across those runs becomes the `lift_uncertainty` for each segment, and pairwise assignment overlap (Jaccard similarity) across runs becomes a `stability_score`. If a segment's stability score is low, we flag it as unreliable — even if the lift looks large — because the cluster boundary is not stable enough to trust.

---

## Isolation Forest Anomaly Detection

**What problem it solves:** Flags individual days in the experiment that look like data-quality problems — bot floods, pipeline outages, sudden metric definition changes — before they contaminate the statistical analysis.

**How it works:** IsolationForest fits a random ensemble of trees; it isolates points (days) by randomly choosing a feature and a split threshold until the point is alone, then scores how many splits were needed — anomalous points are isolated quickly with fewer splits. We use `score_samples()` with a Tukey-fence threshold (Q1 − 3×IQR) rather than the built-in `predict()` to avoid the class-level contamination assumption that forces at least one outlier to be flagged on every dataset.

**When NOT to use it:** When you have fewer than 7 days of data — the fence calculation is unstable, and the model cannot learn what "normal" looks like from a handful of points.

**What it assumes about your data:** Normal days cluster together in feature space; anomalous days are genuinely different across multiple dimensions (metric level, volume, and ratio), not just high-variance draws from the same distribution.

**Interview Q&A:**
> *Why use IsolationForest instead of a simple z-score threshold?*
>
> A z-score flags days that are unusual on one metric in isolation. A day might look normal on volume but simultaneously have an unusual metric-ratio and a metric-level spike — the combination is anomalous even when no single dimension crosses 3σ. IsolationForest uses all four features jointly (control metric, treatment metric, n_control, n_treatment) and detects multi-dimensional outliers that univariate checks miss. It also handles non-Gaussian distributions better, since experiment traffic often has weekday/weekend periodicity that skews the distribution.

---

## CUSUM Drift Detection

**What problem it solves:** Detects whether the gap between treatment and control metrics is trending upward or downward over the experiment — a symptom of mid-experiment interference, seasonality, or a confounding product change.

**How it works:** Each day's treatment-minus-control gap is standardised by subtracting the mean gap (to remove the constant ATE offset) and dividing by the gap's standard deviation. A two-sided cumulative sum (CUSUM) chart then accumulates positive and negative deviations separately, resetting to zero whenever the sum goes negative/positive. A crossing of the threshold signals that a persistent drift has been detected.

**When NOT to use it:** When the experiment has fewer than 10 days — the standardisation parameters are estimated from too few points to be reliable, and the CUSUM will spuriously trigger.

**What it assumes about your data:** Under the null hypothesis (no drift), the standardised gaps are approximately i.i.d. and mean-zero; the threshold of 10 in standardised units is calibrated to be conservative.

**Interview Q&A:**
> *Why mean-centre the gap before running CUSUM?*
>
> Without centering, a constant treatment effect (ATE ≠ 0) causes the gap to perpetually sit above zero, which continuously accumulates in the positive CUSUM and eventually crosses the threshold — giving false "drift detected" signals even when the treatment effect is perfectly stable. By subtracting the mean gap first, the CUSUM only accumulates deviations *around* the treatment effect, so it only fires when the gap is genuinely changing over time, not just non-zero.

---

## Sample Ratio Mismatch (SRM)

**What problem it solves:** Detects whether the proportion of users assigned to treatment matches the intended split — a mismatch indicates a broken randomisation mechanism that invalidates all statistical inference.

**How it works:** Total control and treatment counts are aggregated across all days. A chi-squared goodness-of-fit test compares the observed 2×2 contingency table [observed_treatment, observed_control; expected_treatment, expected_control] against the intended split (default 50/50). A p-value below 0.01 is flagged as SRM.

**When NOT to use it:** When the experiment intentionally uses an unequal split — in that case, pass the correct `expected_ratio` to avoid false positives.

**What it assumes about your data:** Subjects are independently and identically randomised; the expected ratio is specified correctly and is constant over the experiment window.

**Interview Q&A:**
> *An SRM is detected in your A/B test. What do you do next?*
>
> First, halt all analysis — statistical tests on an SRM dataset produce biased estimates and invalid p-values because the two groups are no longer comparable. Next, audit the assignment pipeline: common causes include deterministic bucketing bugs (e.g., hash function collisions), caching that replays a prior assignment, client-side de-duplication that differs by variant, and bot traffic that disproportionately lands in one arm. Once the root cause is identified and fixed, the experiment must be restarted from scratch — you cannot salvage SRM-contaminated results even by excluding the affected window.

---

## Novelty Effect Detection

**What problem it solves:** Distinguishes whether an early treatment lift is genuine (stable, safe to ship) or caused by novelty excitement that will decay once users get used to the change.

**How it works:** A weighted linear regression (weights = 1/SE²) is fit to the daily lift time series, giving more influence to high-volume days with lower standard errors. The slope and its 95% confidence interval classify the trajectory as STABLE (CI overlaps zero), NOVELTY (significant negative slope with positive initial lift), or LEARNING (significant positive slope). For NOVELTY, we project when the effect will reach 10% of its initial value to give a "days to steady-state" estimate.

**When NOT to use it:** When the experiment has run fewer than 7 days — the regression is underpowered, and the pattern cannot be reliably distinguished from noise.

**What it assumes about your data:** Daily lift estimates are available with their standard errors; the true trajectory is approximately linear over the experiment window (piecewise-linear patterns, like a sharp initial spike followed by a plateau, will be fit as a gentle slope).

**Interview Q&A:**
> *How do you tell the difference between a novelty effect and genuine seasonal variation?*
>
> Both produce a declining trend, but they differ in timing and shape. A novelty effect starts high on day 1 and decays monotonically; seasonal variation fluctuates with weekday/weekend patterns or external events and does not start at a peak. In practice we look at the slope confidence interval — if the CI excludes zero and the initial lift is well above the projected stable lift, it is consistent with novelty. Seasonal variation typically shows multiple crossings of the mean, not a clean directional trend. For borderline cases, the CUSUM check runs alongside novelty detection; if CUSUM also fires, that supports an external-event explanation rather than novelty.

---

## Weighted Linear Regression for Effect Trajectory

**What problem it solves:** Estimates the rate at which a treatment effect is growing or decaying over time, accounting for the fact that early days often have fewer users and therefore noisier estimates.

**How it works:** Ordinary least squares is extended by assigning each day a weight of 1/SE², so days with tighter confidence intervals (more traffic) pull the regression line more strongly than high-noise early days. The slope and its standard error are computed analytically from the weighted normal equations, and a t-test with (n−2) degrees of freedom gives the confidence interval on the slope.

**When NOT to use it:** When daily sample sizes are roughly equal across the experiment — in that case, all weights are nearly identical and weighted regression reduces to plain OLS, adding no benefit.

**What it assumes about your data:** The relationship between day number and daily lift is approximately linear; standard errors are valid proxies for measurement uncertainty (they scale inversely with the square root of daily sample size).

**Interview Q&A:**
> *Why use inverse-variance weighting (1/SE²) rather than sample-size weighting (n)?*
>
> Both are common meta-analysis approaches, but they differ when the variance does not scale linearly with sample size. For proportion outcomes, variance = p(1−p)/n, so 1/SE² ∝ n and the two approaches agree. For mean outcomes with heterogeneous population variance, 1/SE² correctly down-weights days where the outcome is intrinsically more variable (e.g., high-variance users showed up that day), whereas raw n weighting would over-count those days. Inverse-variance weighting is the theoretically correct approach for combining heterogeneous estimates, which is why it is the standard method in clinical meta-analysis.
