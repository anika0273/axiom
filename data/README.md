# Axiom Synthetic Demo Datasets

Three independent datasets, each designed to tell a different story and activate different analytical techniques in the Axiom pipeline. They are not subsets of a single large dataset — each has its own business context, distribution choices, and deliberate design decisions.

---

## Why three separate datasets?

Real experimentation platforms run hundreds of experiments simultaneously, each with different metrics, populations, and business questions. A single monolithic dataset would obscure the range of patterns the platform can handle. Three separate datasets let each story stay clean:

- **E-Commerce** shows a clear winner with heterogeneous treatment effects by device type
- **SaaS** demonstrates how variance reduction (CUPED) can flip a borderline decision
- **Marketplace** shows what a broken experiment looks like and why that matters

---

## Dataset 1: E-Commerce Checkout Redesign

**File:** `ecommerce_checkout.csv`  
**Experiment type:** Proportion (binary conversion)  
**Sample size:** 5,000 control + 5,000 treatment = 10,000 total

### Business context

An e-commerce company tests a simplified single-page checkout flow against their current multi-step checkout. The primary question: does the new checkout increase the percentage of users who complete a purchase?

### What story it tells

The new checkout works — but it works much better for mobile users than desktop users. The platform's HTE module discovers this automatically via SHAP feature importance. The segment analysis finds two stable clusters: high-response mobile users and low-response desktop users. This is the kind of finding that tells a product team where to focus next.

There is also a small novelty effect in the first 7 days — users notice the new interface and engage with it slightly more than they will long-term. The novelty detection module flags this, which is important context for interpreting the result.

### Distribution choices and why

| Choice | Rationale |
|--------|-----------|
| Bernoulli outcome | Each user either converts (1) or doesn't (0). This is the standard for checkout experiments. |
| Exponential tenure distribution | Most users are relatively new; a few have been around for years. Exponential matches observed signup curves. |
| Zero-inflated cart value | 25% of users are just browsing with empty carts. These users have near-zero conversion probability regardless of checkout design. |
| Lognormal cart value | Real purchase amounts are right-skewed — many small purchases, occasional large ones. |
| Normal noise on treatment effect | The treatment effect isn't constant across users, even within device type. There's natural variation. |

### Realism injected

- Day-of-week traffic variation (weekday peak, weekend dip for B2C)
- Device-type heterogeneity in treatment response (published benchmark)
- Novelty spike in first 7 days with exponential decay
- Pre-experiment covariate correlated ~0.55 with post-experiment outcome (realistic for 30-day pre-period on conversion)
- Outliers in cart values at 2% rate (power users, bots)

### What synthetic data cannot capture

- Actual cart abandonment patterns (where in the flow users drop off)
- Page load time effects on conversion
- Payment method preferences by demographic
- Return customer recognition and personalization effects
- External events (promotional emails, competitor changes)
- Mobile app vs mobile web differences

### Column definitions

| Column | Type | Range | Description |
|--------|------|--------|-------------|
| `subject_id` | string | `ecom_000000`–`ecom_009999` | Unique pseudonymous user ID |
| `variant` | int | 0 or 1 | 0 = current multi-step checkout, 1 = new single-page checkout |
| `outcome` | float | 0 or 1 | 1 = completed purchase, 0 = did not complete |
| `device_type` | float | 0, 1, 2 | 0 = mobile (40%), 1 = tablet (20%), 2 = desktop (40%) |
| `user_tenure_days` | float | 1–730 | Days since first visit, exponential distribution |
| `cart_value` | float | 0–500+ | Value of items in cart; 25% zero (browsing only) |
| `is_returning_user` | float | 0 or 1 | Whether user has purchased before |
| `pre_experiment_outcome` | float | 0 or 1 | Whether user converted in the 30-day pre-period |
| `experiment_day` | int | 1–30 | Day of experiment the user was exposed |

### Techniques activated

| Technique | Why it activates |
|-----------|-----------------|
| Z-test | Binary proportion outcome |
| Bayesian (Beta-Binomial) | Binary proportion outcome with Beta(1,1) prior |
| CUPED | `pre_experiment_outcome` column present; ~0.55 pre-post correlation |
| Sequential (O'Brien-Fleming) | `experiment_day` column present; 30 days of data |
| Anomaly detection | Daily time series reveals novelty spike days 1–7 |
| Novelty detection | Treatment effect trajectory shows decay toward steady state |
| HTE (XGBoost + SHAP) | `device_type`, `user_tenure_days`, `cart_value` feature columns |
| Segment discovery (k-means + Jaccard) | Same feature columns; mobile vs desktop creates 2 stable clusters |

---

## Dataset 2: SaaS Onboarding Checklist

**File:** `saas_onboarding.csv`  
**Experiment type:** Proportion (binary conversion)  
**Sample size:** 5,000 control + 5,000 treatment = 10,000 total

### Business context

A B2B SaaS company tests an interactive onboarding checklist against their current empty dashboard. New trial users are either shown the checklist (with guided setup tasks) or the blank dashboard. The metric is trial-to-paid conversion within 30 days.

### What story it tells

This is the most important demonstration in the platform. Without CUPED, the result is *not statistically significant* (p ≈ 0.061). With CUPED variance reduction applied, it *is* significant (p ≈ 0.028). The checklist should be shipped — but only if you run the right analysis.

This demonstrates that variance reduction is not a statistical nicety. It can determine whether a product gets built or abandoned.

### Why we engineered a borderline result

The p-value near 0.06 was deliberate. It creates a scenario where:
- A naive analyst says "not significant, don't ship"
- An analyst with CUPED says "significant, ship it"
- Both are looking at the same data

This forces a conversation about methodology that most dashboards never surface. Axiom surfaces it automatically.

The mechanism: users who converted before the experiment (high `pre_experiment_outcome`) are likely to convert again regardless of treatment. Their variance adds noise that obscures the real signal. CUPED removes that noise by adjusting for the pre-period covariate, reducing variance by ~42% and pushing the result over the significance threshold.

### Heterogeneity: enterprise vs SMB

Enterprise users (company size > 100) benefit ~5x more from the checklist than small businesses. The reasons are intuitive: enterprise teams have multiple stakeholders who need to reach consensus on adoption, and the checklist gives them a shared vocabulary and progress tracker. Solo founders at small companies just want to try the product directly.

The HTE module discovers this divide automatically. The segment discovery module finds two stable clusters corresponding closely to enterprise and SMB.

### Column definitions

| Column | Type | Range | Description |
|--------|------|--------|-------------|
| `subject_id` | string | `saas_000000`–`saas_009999` | Unique pseudonymous user ID |
| `variant` | int | 0 or 1 | 0 = empty dashboard, 1 = onboarding checklist |
| `outcome` | float | 0 or 1 | 1 = converted to paid, 0 = did not convert |
| `company_size` | float | 1–10000 | Number of employees, lognormal distribution |
| `days_since_signup` | float | 1–90 | Days since trial started, exponential distribution |
| `plan_type` | float | 0, 1, 2 | 0 = free, 1 = trial, 2 = paid |
| `feature_usage_count` | float | 0–25+ | Features used in first week, Poisson distribution |
| `pre_experiment_outcome` | float | 0 or 1 | Whether user converted in the previous trial cohort |
| `experiment_day` | int | 1–30 | Day of experiment the user was exposed |

### Techniques activated

| Technique | Why it activates |
|-----------|-----------------|
| Z-test | Binary proportion outcome |
| Bayesian (Beta-Binomial) | Binary proportion outcome |
| CUPED | **Changes the decision.** `pre_experiment_outcome` present; ~0.65 pre-post correlation |
| Sequential | `experiment_day` present; 30 days |
| Anomaly detection | Daily time series; no anomalies by design (stable UI change) |
| Novelty detection | No decay — checklist is a persistent UI element, not a novelty |
| HTE (XGBoost + SHAP) | `company_size`, `days_since_signup`, `plan_type`, `feature_usage_count` |
| Segment discovery | Company size creates 2 clear clusters: enterprise and SMB |

---

## Dataset 3: Marketplace Fee Reduction

**File:** `marketplace_fee.csv`  
**Experiment type:** Mean (continuous GMV)  
**Sample size:** 4,500 control + 5,500 treatment = 10,000 total

### Business context

An online marketplace reduces the seller transaction fee from 8% to 5%, hypothesizing that lower fees will drive higher gross merchandise value (GMV) per seller. The primary metric is total GMV in the 30-day experiment window.

### Why it is intentionally broken

This experiment has two compounding problems:

**Problem 1: Sample ratio mismatch (SRM)**  
The target split was 50/50. The actual split is 45/55. Larger, more established sellers heard about the fee reduction through informal channels before the experiment launched and self-selected into the treatment group. The treatment group is not a random sample of sellers — it is a systematically different population.

This is a real problem in marketplace experiments. Sellers are often interconnected through forums, Slack communities, and industry newsletters. Keeping treatment assignment secret is harder than in consumer experiments.

The SRM detection module flags this within seconds. Without it, you would never notice the problem from the p-value alone — the experiment would look significant, and you would make a decision based on biased data.

**Problem 2: Strong novelty effect**  
When fees drop, sellers immediately rush to list more items. GMV spikes dramatically in the first 5 days, then decays toward a new steady state over 2 weeks. The observed lift during the novelty window is approximately $7, but the true sustainable lift is approximately $4. If you analyze results at day 7, you will overestimate the benefit by ~75%.

The novelty detection module identifies this decay pattern and warns that early results may not be representative.

### Why a broken experiment teaches more than a clean one

Every analyst knows what a significant result looks like. Fewer have seen what a broken one looks like before it's too late. This dataset gives analysts experience recognizing:
- What SRM looks like in the numbers (asymmetric groups, selection bias)
- What novelty decay looks like in a time series (high early, stabilizing)
- Why "significant" and "trustworthy" are different things

The correct decision for this experiment is: **do not ship, redesign the experiment** with pre-registration and blinded assignment. The true fee reduction effect is real but the measurement cannot be trusted.

### Column definitions

| Column | Type | Range | Description |
|--------|------|--------|-------------|
| `subject_id` | string | `mkt_000000`–`mkt_009999` | Unique pseudonymous seller ID |
| `variant` | int | 0 or 1 | 0 = 8% fee (control), 1 = 5% fee (treatment) |
| `outcome` | float | 0–2000+ | Total GMV in experiment window ($), lognormal + outliers |
| `seller_tenure_days` | float | 1–1825 | Days since seller joined marketplace |
| `avg_listing_price` | float | 1–500 | Average price of items listed, lognormal |
| `listings_count` | float | 0–40+ | Number of active listings, Poisson |
| `category_id` | float | 0–9 | Product category (proxy feature) |
| `pre_experiment_outcome` | float | 0+ | GMV in the prior 30-day period ($) |
| `experiment_day` | int | 1–30 | Day seller first exposed to new fee |

### Techniques activated

| Technique | Result |
|-----------|--------|
| Welch t-test | Significant — but untrustworthy due to SRM |
| Bayesian (Normal-CLT) | High probability treatment better — but biased |
| CUPED | Activates (pre_experiment_outcome present); still biased by SRM |
| Sequential | Activates; early looks show inflated effect |
| Anomaly detection | Flags variance instability from outliers and novelty |
| Novelty detection | **Strong decay pattern detected** — effect trajectory declines |
| HTE | Veteran sellers (tenure > 365) show 2x response |
| Segment discovery | High-tenure vs new-seller clusters emerge |
| **SRM detection** | **FAILS — broken assignment flagged in warnings** |

---

## How synthetic data differs from real data

### What we can simulate

- Distribution shape (normal, lognormal, Poisson, Bernoulli)
- Heterogeneous treatment effects by observable features
- Day-of-week traffic patterns
- Novelty effects with designed decay curves
- Pre-experiment covariate correlation
- Outliers at specified rates
- Broken randomization (by design)
- Zero-inflated outcomes

### What we cannot simulate

| Real-world phenomenon | Why it matters |
|-----------------------|---------------|
| Unknown confounders | Real data has variables we never measured that affect the outcome |
| External events | Competitor promotions, news events, algorithm changes happen mid-experiment |
| Measurement error | Duplicate events, delayed attribution, pipeline bugs |
| Non-stationary effects | Treatment effects that change as the market adapts |
| Social spillover | Control users talking to treatment users and changing their behavior |
| Survivorship bias | Users who churned before the experiment cannot be included |
| Selection into the experiment | Real assignment mechanisms are rarely perfectly random |

### Why "too clean" is a problem

Our synthetic data has cleaner treatment effects, more stable time series, and more separable segments than real data. This means:

- CUPED variance reduction may appear stronger than it would in practice
- Segment boundaries may be sharper than real clusters
- Novelty decay may follow a smoother curve than real user behavior
- HTE SHAP values may point to cleaner feature importance than reality

Real experiments are messier. The platform handles real data well, but the demo datasets show idealized versions of each pattern. Treat them as illustrations, not guarantees.

### How realism was injected

Despite the above limitations, we made specific choices to avoid the most artificial patterns:

1. **Right-skewed distributions** — Revenue and engagement metrics use lognormal distributions, not normal. Real purchase amounts are never symmetric.

2. **Zero inflation** — 25% of e-commerce users have empty carts. Conversion experiments on a fully engaged population overstate how checkouts perform in practice.

3. **Correlated noise on treatment effects** — The effect isn't a constant shift for all users. We add per-user noise that is correlated with their features, creating the messier heterogeneity that real data shows.

4. **Day-of-week variation** — Weekend traffic dips are built into the daily time series. Experiments that run over weekends show this pattern in the anomaly module.

5. **Outliers** — 2–3% of users have extreme values (power users, bots, data errors). These affect mean estimation and are realistic at that rate.

6. **Partial novelty effects** — The e-commerce novelty spike is small and decays quickly. The marketplace spike is large and decays slowly. These reflect published patterns for UI changes vs economic incentives respectively.

---

## How to regenerate the data

### Generate all three datasets and save to disk

```bash
python scripts/generate_synthetic_data.py --save-only
```

### Upload existing CSVs to Axiom (backend must be running)

```bash
python scripts/generate_synthetic_data.py --upload-only
```

### Generate and upload in one step

```bash
python scripts/generate_synthetic_data.py
```

### Generate only one dataset

```bash
python scripts/generate_synthetic_data.py --experiment ecommerce --save-only
python scripts/generate_synthetic_data.py --experiment saas --save-only
python scripts/generate_synthetic_data.py --experiment marketplace --save-only
```

### Changing parameters

The key constants are at the top of `scripts/generate_synthetic_data.py`:

```python
N_DAYS = 30        # experiment duration (affects sequential and novelty modules)
N_PER_GROUP = 5_000  # subjects per group (affects power and CUPED clarity)
BATCH_SIZE = 5_000   # upload batch size (do not exceed 5000 -- PG parameter limit)
```

The RNG seed is fixed at `2026` for reproducibility. Change it to get a different random realization of the same distributions.

### Adding a new experiment

1. Create an experiment in Axiom via the UI or API
2. Write a new `generate_<name>(rng)` function following the pattern above
3. Include `pre_experiment_outcome` for CUPED, `experiment_day` for sequential/novelty, and feature columns for HTE/segments
4. Add an entry to the `datasets` dict in `main()`
5. Run `python scripts/generate_synthetic_data.py --experiment <name>`
