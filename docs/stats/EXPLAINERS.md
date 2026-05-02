# Stats Engine — Method Explainers

Each section covers one statistical method implemented in `backend/app/stats/`.
Format: problem → mechanism → when not to use → interview Q&A.

---

## Two-Proportion Z-Test

**What problem it solves**
Determines whether two binary conversion rates (e.g. click-through, purchase, sign-up) differ by more than chance.

**How it works**
Under the null hypothesis that control and treatment have the same true rate, the pooled proportion gives a standard error for the observed difference; dividing the difference by that standard error produces a z-statistic that follows a standard normal distribution for large samples. Values beyond ±1.96 (α=0.05, two-tailed) are declared significant.

**When NOT to use it**
- Either group has fewer than 5 expected successes or failures (normal approximation breaks down; use Fisher's exact test instead).
- The rate is very close to 0 or 1 (boundary effects make the normal approximation unreliable).
- Observations are paired or matched across variants (use McNemar's test).
- You need to correct for pre-experiment imbalance in conversion propensity (use CUPED instead).

**Interview question**
*"What's the difference between a one-tailed and two-tailed z-test, and which should you use for A/B tests?"*

A two-tailed test asks "is there any difference?" and splits α equally across both tails; a one-tailed test asks "is treatment strictly better?" and concentrates all α in one direction. Always use two-tailed for A/B tests: the treatment can also make things worse, and you need to know that. One-tailed tests are only appropriate when a negative result is operationally impossible — which is never true in practice.

---

## Welch's T-Test

**What problem it solves**
Tests whether the means of two continuous-metric groups differ when the groups may have unequal variances — the correct default for revenue, session duration, items added, and any other non-binary outcome.

**How it works**
Instead of pooling the two group variances (as Student's t does), Welch's test computes a separate variance estimate for each group and adjusts the effective degrees of freedom using the Welch-Satterthwaite equation, producing a t-statistic whose null distribution is well-approximated even when σ_control ≠ σ_treatment. The result is strictly more general than Student's t and converges to it when variances are equal.

**When NOT to use it**
- True ratio metrics where the numerator and denominator are not independent per user (e.g. total_revenue / total_sessions across users with variable session counts — use the delta method).
- Count data dominated by zeros with a highly skewed distribution and very small N (consider Mann-Whitney as a nonparametric alternative, accepting lower power).
- The outcome has extreme outliers that inflate variance so severely that the CLT hasn't kicked in at the observed N (winsorize or use a log transform first).

**Interview question**
*"Why does Axiom use Welch's t-test rather than Student's t-test?"*

Student's t-test assumes σ_control = σ_treatment. In practice this is almost never true — the treatment changes behavior, which changes variance. Welch's t-test makes no equal-variance assumption and has essentially zero power cost when variances happen to be equal. Using Student's t when variances differ can inflate or deflate the Type I error rate unpredictably. Welch's is the correct default; Student's t is only appropriate when equal variance is known from domain knowledge, not assumed for convenience.

---

## CUPED (Controlled-experiment Using Pre-Experiment Data)

**What problem it solves**
Reduces the variance of the experiment estimator using pre-experiment user behavior, letting you reach the same statistical power with fewer subjects — or equivalently, shorter runtimes — without introducing bias.

**How it works**
For each user, a pre-experiment covariate (e.g. last month's conversion) is regressed on the experiment-period outcome via ordinary least squares; the fitted slope θ is used to subtract the predictable component of each user's outcome before computing group means. Because random assignment ensures the covariate averages equally across control and treatment, this subtraction cancels out in the difference — the estimated effect is unchanged — but the within-group variance shrinks by a factor of (1 − ρ²), where ρ is the pre-post correlation.

**When NOT to use it**
- No pre-experiment covariate data exists for users.
- The covariate was measured after experiment start (introduces post-treatment bias — CUPED does not fix confounding).
- Pre-post correlation |ρ| < 0.3; the variance reduction is less than 9%, which rarely justifies the added complexity.
- Assignment is not random; CUPED cannot correct for selection bias.
- The experiment is so short that there is no meaningful prior-period window (e.g. a 24-hour test for new users).

**Interview question**
*"Does CUPED change the expected value of the treatment effect estimate?"*

No. Because of random assignment, E[X_control] ≈ E[X_treatment] ≈ E[X] — the covariate mean is the same in both groups in expectation. The CUPED adjustment subtracts θ·(X_i − X̄) from every user, so both group means shift by exactly the same amount, and their difference is unchanged. CUPED only shrinks variance; it never moves the point estimate. This is the key property that keeps the test unbiased — if assignment were non-random, that equality would not hold and CUPED would introduce bias.

---

## O'Brien-Fleming Sequential Testing

**What problem it solves**
Allows safe interim looks at accumulating experiment data so that you can stop early when a clear winner (or clear futility) emerges, without inflating the false positive rate above the pre-specified α.

**How it works**
An alpha-spending function is fixed before the experiment starts; it allocates the α budget across K planned looks in proportion to the information fraction already accumulated. Early looks require an extremely large z-statistic to cross the efficacy boundary (the boundary at 10% information is roughly three times the final-look critical value), while the last look uses approximately the standard threshold — so if the experiment runs to completion, the result is interpreted almost identically to a fixed-horizon test. Crossing any boundary at any look controls the experiment-wide false positive rate at exactly α.

**When NOT to use it**
- The experiment has already completed data collection (just run the standard fixed-horizon test; sequential methods add nothing post hoc).
- Only one look is planned (use the standard test directly; the sequential machinery is unnecessary overhead).
- The experiment is extremely short (hours) where early boundaries would be impossibly conservative and would never be crossed in practice.
- You need to add more looks than originally planned mid-experiment (the alpha budget must be re-computed; unplanned looks are not free).

**Interview question**
*"Why can't you just check p < 0.05 at multiple interim points and stop when you hit significance?"*

Each independent check at α=0.05 has a 5% chance of a false positive. With 10 truly independent checks, the probability of at least one false positive is 1 − 0.95¹⁰ ≈ 40%. Worse, A/B experiment looks share subjects and are positively correlated, so the inflation is not simply additive — but it is still severe. Sequential methods like O'Brien-Fleming pre-commit to a spending function that borrows future alpha and pays it back across looks, keeping the cumulative Type I error at exactly the nominal level no matter how many interim looks you take.

---

## Multiple Comparisons Corrections

### Bonferroni

**What problem it solves**
Controls the family-wise error rate (FWER) — the probability that *any* of the tested metrics produces a false positive — by making the per-metric threshold stricter.

**How it works**
Each p-value is compared against α/m, where m is the number of metrics being tested. This guarantees that, even under the worst-case scenario (all nulls are true), the chance of at least one false rejection is at most α. The method is maximally conservative and makes no assumptions about how metric p-values correlate with each other.

**When NOT to use it**
- Testing more than ~20 metrics; the threshold becomes so stringent that almost no real effects survive.
- An exploratory analysis where controlling the false discovery rate is more appropriate than controlling the family-wise rate.
- Holm is available: Bonferroni is uniformly dominated by Holm-Bonferroni in every scenario (Holm rejects at least as many hypotheses and maintains the same FWER guarantee), so Bonferroni is only useful as an explanatory benchmark.

### Holm-Bonferroni (Step-Down)

**What problem it solves**
Controls FWER like Bonferroni but recovers additional power by applying stricter thresholds to smaller p-values and relaxing them for larger ones, in a stepwise procedure.

**How it works**
P-values are sorted ascending and compared against thresholds α/m, α/(m−1), …, α/1 in sequence; as soon as a p-value fails its threshold, all remaining (larger) p-values are also kept as non-significant. This step-down structure is always at least as powerful as Bonferroni — it can reject hypotheses that Bonferroni would keep, and never rejects fewer.

**When NOT to use it**
- An exploratory analysis with many metrics where FDR control is more appropriate.
- The number of metrics is so large (> 50) that even Holm's step-down gains are insufficient to maintain useful power (use BH instead).

### Benjamini-Hochberg (FDR)

**What problem it solves**
Controls the false discovery rate (FDR) — the expected fraction of rejected hypotheses that are false positives — rather than the probability of any false positive, yielding substantially more power when testing many metrics.

**How it works**
P-values are sorted ascending; the largest k such that p_(k) ≤ (k/m)·α is found, and all hypotheses ranked 1 through k are rejected. This adaptive threshold is looser than Bonferroni's and grows with rank, so genuinely small p-values get a less penalizing comparison. The procedure is valid (FDR ≤ α) whenever metric test statistics are positively dependent — which they almost always are in A/B tests (conversion rate, revenue, and session length all tend to move together when the treatment works).

**When NOT to use it**
- A confirmatory trial where even a single false positive has serious consequences (use Bonferroni or Holm, which control FWER).
- Metrics are strongly negatively correlated (the PRDS assumption fails; use the Benjamini-Yekutieli correction instead, though it is rarely needed in practice).

**Interview question (covers all three)**
*"What's the difference between FWER and FDR, and why does Axiom default to BH?"*

FWER (family-wise error rate) is P(at least one false positive across all tests). FDR is E[false positives / total rejections]. FWER is strictly more conservative: controlling it at 5% means at most a 5% chance of any mistake; controlling FDR at 5% means on average 5% of your declared winners are false. Axiom defaults to BH because most experiments test 3–15 metrics that are positively correlated (conversion and revenue both respond to a good treatment), and FDR control is appropriate for product experimentation where the cost of occasional false positives is low compared to the cost of missing real effects. For confirmatory, high-stakes decisions, Holm is offered as the FWER alternative.

---

## Power Analysis and Sample Size Calculation

**What problem it solves**
Determines the minimum number of subjects required to detect a pre-specified minimum detectable effect (MDE) with a given false positive rate α and statistical power (1−β) before the experiment starts.

**How it works**
The power formula for a two-proportion test is inverted analytically: given α (typically 0.05), power (typically 0.80), and the MDE expressed as Cohen's d (a dimensionless effect size), the required per-group sample size is solved in closed form using the quantiles of the standard normal distribution. A power curve is also computed over a range of effect sizes to show how power degrades as the true effect shrinks below the MDE.

**When NOT to use it**
- Running a continuous (always-on) experiment without a fixed endpoint — use sequential methods with an information-fraction stopping rule instead.
- The metric is so heavily skewed that the normal approximation for the mean test is not valid at the planned N (simulate power instead of computing it analytically).
- You are conducting a multi-arm test — power calculations for pairwise comparisons ignore the global FWER and underestimate the required sample size.

**Interview question**
*"What happens to required sample size if you halve the minimum detectable effect?"*

Sample size scales with 1/δ² (where δ is the effect size), so halving the MDE quadruples the required sample size. This is the most important formula in experimental design: small improvements are exponentially more expensive to detect. If an experiment targeting a 5% lift needs 10,000 users per group, targeting a 2.5% lift needs ~40,000. This is why setting a realistic MDE — not "as small as possible" — is critical for planning a feasible experiment.

---

## Delta Method (Ratio Metrics)

**What problem it solves**
Estimates the standard error of a ratio statistic (e.g. revenue per session = total revenue / total sessions) when the numerator and denominator are correlated user-level random variables, so that a valid t-test can be run on the ratio.

**How it works**
A first-order Taylor expansion approximates the variance of a ratio f(A, B) = A/B as a linear combination of Var(A), Var(B), and Cov(A, B), weighted by the partial derivatives of f evaluated at the sample means. This gives a consistent standard error estimate for the ratio without requiring access to the ratio's exact sampling distribution, and the resulting statistic is approximately normal by the CLT.

**When NOT to use it**
- The denominator is very small or zero for many users (the approximation is unreliable when the denominator variance dominates).
- You have true user-level ratio data (each user has exactly one event) — in that case, Welch's t-test on individual ratios is simpler and equally valid.
- The sample size is so small that the CLT approximation for the ratio has not kicked in (bootstrap the standard error instead).

**Interview question**
*"Why can't you just compute revenue/sessions for each user and run a t-test on those values?"*

For most setups you can, and it works well. The delta method matters specifically when the ratio is computed at the *aggregate* level — total revenue divided by total sessions — where users contribute different numbers of sessions. A user with 200 sessions influences the denominator (and therefore the ratio) far more than a user with 2 sessions, creating heteroskedasticity that a naive per-user ratio ignores. The delta method correctly propagates this variance structure, producing valid confidence intervals for the aggregate ratio estimator.
