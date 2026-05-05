# ML Engine — Design Decisions

## Why XGBoost + interaction terms for HTE instead of causal forests?

**Choice:** XGBoost with explicit `feature × treatment` interaction columns, plus SHAP on the interaction terms.

**Alternatives considered:**
- **EconML CausalForestDML** (double machine learning + honest random forest)
- **R `grf` package** via rpy2 (gold standard for causal forests in academia)
- **Meta-learners (T-learner, S-learner, X-learner)** with any base model

**Why this approach for Axiom:**
Causal forests are theoretically superior when the data is observational and confounding is a genuine concern. Axiom's data is always from randomised A/B experiments — randomisation already handles confounding, so the incremental statistical correctness of honest splitting is marginal. XGBoost + SHAP gives us three practical wins that matter for an API-first product: (1) SHAP's TreeExplainer runs in milliseconds and produces interpretable interaction rankings for the dashboard; (2) XGBoost is a stable, well-tested dependency with no R FFI complications; and (3) the interaction-term approach is transparent — a reviewer can inspect exactly which columns encode treatment effects without understanding forest internals. The CLAUDE.md constraint that stats code must be auditable by a non-ML reviewer further favoured the explicit-interaction approach over a black-box causal model.

---

## Why KMeans instead of DBSCAN or GMM for segments?

**Choice:** KMeans with silhouette-optimal k (k = 2 to 8), with assignment-stability scoring across five independent runs.

**Alternatives considered:**
- **DBSCAN** — density-based, discovers arbitrary shapes, k-free
- **Gaussian Mixture Models (GMM)** — soft assignments, handles elliptical clusters, proper probabilistic framework
- **Hierarchical clustering (Ward linkage)** — dendrogram gives natural stopping criterion

**Why this approach for Axiom:**
KMeans has two properties that are non-negotiable for our use case. First, it produces hard cluster assignments, which means every user belongs to exactly one segment — a requirement for clean per-segment significance tests. GMM's soft assignments require a threshold decision to assign users, introducing a tuning knob with no obvious optimal value. Second, KMeans centroids are fully interpretable: the top features distinguishing a cluster are simply the dimensions where the centroid differs most from the global mean, which maps directly to the "segment description" in the UI. DBSCAN was ruled out because its density parameter is hard to tune across experiments with wildly different user counts (5,000 to 500,000), and it produces noise points that cannot be profiled. The silhouette-selection loop keeps k bounded and avoids over-segmentation on small experiments.

---

## Why IsolationForest instead of LOF or z-score for outliers?

**Choice:** IsolationForest on the 4-dimensional daily feature vector, with a Tukey-fence threshold on `score_samples()` rather than `predict()`.

**Alternatives considered:**
- **Local Outlier Factor (LOF)** — distance-based, context-aware, handles multi-modal distributions
- **Univariate z-score per feature** — one threshold per metric column, flag if any exceeds 3σ
- **CUSUM on raw daily volume** — already used separately for drift, not identical to point anomalies

**Why this approach for Axiom:**
LOF is theoretically superior for datasets where "normal" has multiple clusters, but it requires a `k`-nearest-neighbour hyperparameter that has no principled default for our domain and it does not scale well as the experiment grows. Z-scores catch univariate anomalies but miss correlated multi-dimensional ones — a day can look normal on volume alone but be anomalous because traffic doubled for control while treatment halved simultaneously. IsolationForest handles the joint distribution across all four columns without a distance-metric choice, runs in O(n log n), and is stable across the range of dataset sizes we expect. The critical design choice was switching from `predict()` to `score_samples()` with a Tukey fence: `predict()` always flags a fixed contamination fraction, which causes false positives on clean datasets (it finds an "outlier" even when all days look identical). The fence only fires when a day is genuinely extreme relative to the rest.

---

## Why weighted regression (1/SE²) instead of plain OLS for novelty?

**Choice:** Weighted least squares with weights = 1/SE², where SE is the daily standard error of the lift estimate (proxied by 1/√n_total).

**Alternatives considered:**
- **Plain OLS** — uniform weights, all days contribute equally
- **LOESS (locally-weighted smoothing)** — non-parametric, handles non-linear trajectories
- **Bayesian state-space model** — posterior over the slope at each day

**Why this approach for Axiom:**
Novelty detection requires a single interpretable slope value with a confidence interval that maps to a plain-English recommendation ("wait N days"). OLS gives the right answer when daily sample sizes are equal, but in practice experiments have smaller samples on early days (before the audience builds up) and on weekends — those days have larger SEs and should influence the slope estimate less. Inverse-variance weighting is the well-established meta-analysis standard for combining heterogeneous estimates: days that deliver more precision get proportionally more weight. LOESS and Bayesian state-space models produce better fits but not an easily interpretable "slope ± CI" that the recommendation logic can act on, and they introduce smoothing hyperparameters with no obvious business-domain defaults. Plain OLS was the baseline, but the user-study data from A/B platform postmortems consistently shows that early-day noise causes OLS to classify stable effects as NOVELTY — the weighted version avoids this.

---

## Why ThreadPoolExecutor instead of asyncio for parallel ML?

**Choice:** `ThreadPoolExecutor(max_workers=2)` to run HTE and segment discovery in parallel, with a synchronous `result()` call that blocks until both complete.

**Alternatives considered:**
- **asyncio.gather with run_in_executor** — non-blocking, integrates with FastAPI's async context
- **ProcessPoolExecutor** — true multiprocessing, avoids the GIL entirely
- **Sequential execution** — simple, no concurrency overhead

**Why this approach for Axiom:**
HTE (XGBoost) and segment discovery (scikit-learn KMeans) both call into C extensions that release the Python GIL for their core computations. This means two threads running these workloads simultaneously achieve genuine wall-clock parallelism without the process-startup overhead of `ProcessPoolExecutor`. `asyncio.gather + run_in_executor` would also work, but it adds `await` syntax and requires the caller to be async-aware — the ML engine is a pure computation layer that should have no I/O concerns. ThreadPoolExecutor gives us the concurrency benefit with a synchronous API that is easier to test, profile, and reason about in isolation. ProcessPoolExecutor was ruled out because pickling large pandas DataFrames and XGBoost models across process boundaries adds latency and serialisation complexity that outweighs the GIL benefit for workloads that already release the GIL.

---

## Why CUSUM for drift instead of Mann-Kendall or t-test on halves?

**Choice:** Two-sided CUSUM (cumulative sum control chart) on the mean-centred, standardised daily gap series.

**Alternatives considered:**
- **Mann-Kendall trend test** — non-parametric rank-based test for monotonic trend
- **Two-sample t-test on first-half vs second-half** — simple, interpretable
- **Linear regression slope test** — slope = 0 null, same data as novelty detection

**Why this approach for Axiom:**
Mann-Kendall is sensitive to monotonic trends but accumulates rank information globally — it cannot pinpoint *when* the drift began, which is the key diagnostic question. A t-test on first vs second half is easy to interpret but arbitrary in the split point: a drift that begins on day 20 of a 28-day experiment will not be detected if the first 19 days are stable. CUSUM is specifically designed for sequential change-point detection; it resets after each crossing so each detected drift event is independent, and it naturally handles the "when did this start" question by noting which day the threshold was crossed. The mean-centering step is the critical design decision: without it, any non-zero ATE causes perpetual accumulation (see EXPLAINERS.md for detail). The threshold of 10 in standardised units was chosen to be conservative — it is unlikely to fire on random noise for the experiment durations (7–90 days) common on this platform.
