# Axiom Demo Datasets

Three synthetic datasets, each designed to tell a different story
and activate different techniques in the analysis pipeline.

---

## Why three separate datasets

Real companies run hundreds of independent experiments — not one
large shared dataset. Each experiment has its own business context,
metric type, and failure mode. Keeping them separate makes each
story cleaner and more explainable.

Each dataset is independently realistic. They do not share subjects
or outcomes.

---

## How synthetic data differs from real data

### What we can simulate
- Realistic outcome distributions (lognormal revenue, binary conversion)
- Day-of-week traffic patterns (lower weekends for B2B products)
- Heterogeneous treatment effects (some users respond, others don't)
- Novelty effects (initial excitement that fades over time)
- Broken randomization (self-selection bias in Marketplace)
- Pre-experiment covariates that correlate with outcomes

### What we cannot simulate
- Unknown confounders — real data has variables we never measured
- External events — competitor launches, holidays, infrastructure outages
- Measurement bugs — duplicate events, late-arriving data, tracking gaps
- Seasonal patterns — real products have weekly and monthly cycles
- User churn during the experiment — some users disappear mid-experiment
- Network effects — treatment of one user affecting another

### How we inject realism
- Right-skewed distributions for revenue (lognormal, not normal)
- Zero-inflation for conversion (many users never convert regardless)
- Day-of-week multipliers on daily traffic (Tuesday peak, Sunday trough)
- Partial heterogeneity — treatment effects are noisy, not perfectly clean
- Outliers at realistic rates (2-5% of users have extreme values)
- Natural trend component (users naturally improve over time)

### The honest limitation
Synthetic data is designed to tell a specific story. In a real
experiment, you do not know in advance whether CUPED will flip
the decision, whether novelty will decay, or whether SRM will
be detected. The demo datasets show the most instructive scenarios
— not guaranteed real-world outcomes.

---

## Dataset 1: E-Commerce Checkout Redesign

**File:** `ecommerce_checkout.csv`
**Experiment type:** Proportion (binary conversion)
**Size:** 10,000 subjects — 5,000 control, 5,000 treatment
**Duration:** 30 days

### Business context
An e-commerce company tests a simplified single-page checkout
against their current multi-step flow. The hypothesis is that
removing friction from the checkout process increases conversion.

### What story it tells
A clean, well-powered experiment with a significant result.
But the average lift hides an important story: mobile users
respond dramatically better than desktop users. Shipping to
all users equally is correct, but the business insight is that
the new checkout was designed for mobile.

### Column definitions

| Column | Type | Range | Description |
|---|---|---|---|
| subject_id | string | ecom_000000–ecom_009999 | Unique user identifier |
| variant | int | 0 or 1 | 0=control (old checkout), 1=treatment (new) |
| outcome | float | 0 or 1 | 1 if user completed purchase |
| device_type | float | 0, 1, 2 | 0=mobile, 1=tablet, 2=desktop |
| user_tenure_days | float | 1–730 | Days since first visit, exponential distribution |
| cart_value | float | 0–500 | Value of items in cart, lognormal, 25% zero |
| is_returning_user | float | 0 or 1 | 1 if user has purchased before |
| pre_experiment_outcome | float | 0 or 1 | Did user convert in 30 days before experiment? |
| experiment_day | int | 1–30 | Day of experiment user was assigned |

### Distribution choices
- **user_tenure_days**: Exponential(scale=60) — most users are
  relatively new, long tail of veteran users. This is realistic
  for e-commerce where most traffic is new or occasional visitors.
- **cart_value**: Lognormal(mean=3.5, sigma=0.8) with 25%
  zero-inflation — most carts are small, a few are large, many
  users browse without adding items. This matches real purchase
  amount distributions.
- **device_type**: 40% mobile, 20% tablet, 40% desktop — typical
  for a mid-size e-commerce site.

### Treatment effect design
- Mobile: +5pp lift (new checkout suits small screens)
- Tablet: +2pp lift
- Desktop: +0.5pp lift (desktop users comfortable with multi-step)
- Novelty effect: small spike days 1-7, stabilizes by day 10
- Overall lift: ~3pp (from 5.4% to 8.3% conversion)

### Techniques activated
All eight techniques fire on this dataset:
- **Z-test** — binary outcome, proportion test
- **Bayesian** — Beta-Binomial model, probability treatment better
- **CUPED** — pre_experiment_outcome as covariate (low correlation for binary, variance reduction minimal — this is honest)
- **Sequential** — O'Brien-Fleming boundaries on daily data
- **Anomaly detection** — 4 checks on daily metric patterns
- **Novelty detection** — OLS on daily effect trajectory
- **HTE** — XGBoost finds device_type as strongest modifier
- **Segment discovery** — K-means clusters by device and tenure

---

## Dataset 2: SaaS Onboarding Checklist

**File:** `saas_onboarding.csv`
**Experiment type:** Mean (continuous activation score)
**Size:** 10,000 subjects — 5,000 control, 5,000 treatment
**Duration:** 30 days

### Business context
A SaaS company tests an interactive onboarding checklist against
their current empty dashboard. The checklist guides new trial
users toward activation milestones (inviting a teammate, creating
a project, connecting an integration). The outcome is an
activation score from 0 to 100 measuring milestone completion.

### What changed from the original design
The experiment was originally designed as a proportion experiment
(binary trial-to-paid conversion). We changed it to a mean
experiment (continuous activation score) for a specific reason:
**CUPED requires meaningful correlation between the pre-experiment
covariate and the outcome. Binary outcomes have a mathematical
ceiling on correlation (~0.35 at 12% base rate) that makes CUPED
variance reduction negligible.**

With a continuous activation score, we achieved pre-post
correlation of 0.629, giving 39.6% variance reduction.

### The central story: CUPED changes the decision
Without CUPED: p = 0.775 — NOT significant — do not ship
With CUPED:    p = 0.034 — SIGNIFICANT    — ship

CUPED changed the business decision. This is the most important
demonstration in the platform. A team running this experiment
without CUPED would conclude the checklist does not work and
abandon it. With CUPED, they would correctly identify a real
effect and ship a feature that improves activation.

### Why the lift is small (+0.12 points on a 0-100 scale)
The average is pulled down by SMB users (85% of sample, company
size ≤ 100 employees) who barely respond (+0.1 points). Enterprise
users (15%, company size > 100) respond strongly (+0.8 points).

The HTE analysis correctly identifies company_size as the strongest
treatment modifier — the same insight the CUPED result implies.

### Why CUPED works here
The pre-experiment activation score captures stable user
characteristics (engagement level, company type, plan type) that
predict post-experiment scores. After removing 39.6% of variance
from these predictable components, the small true effect (+0.12
points) becomes statistically visible.

### Column definitions

| Column | Type | Range | Description |
|---|---|---|---|
| subject_id | string | saas_000000–saas_009999 | Unique user identifier |
| variant | int | 0 or 1 | 0=control (no checklist), 1=treatment (checklist) |
| outcome | float | 0–100 | Activation score during experiment |
| company_size | float | 1–10,000 | Number of employees, lognormal distribution |
| days_since_signup | float | 1–90 | Days since trial started, exponential |
| plan_type | float | 0, 1, 2 | 0=free, 1=trial, 2=paid |
| feature_usage_count | float | 0–25 | Features used in first week, Poisson |
| pre_experiment_outcome | float | 0–100 | Activation score 30 days before experiment |
| experiment_day | int | 1–30 | Day of experiment user was assigned |

### Distribution choices
- **company_size**: Lognormal(mean=3, sigma=1.5) — most companies
  are small (1-20 employees), long tail to enterprises. Realistic
  for a B2B SaaS product.
- **days_since_signup**: Exponential(scale=14) — most trial users
  are recent signups (median ~10 days). Older signups have likely
  already converted or churned.
- **plan_type**: 50% free, 35% trial, 15% paid — typical freemium
  funnel distribution.

### Honest limitations
- The +0.65 baseline shift on the treatment group was engineered
  to guarantee the p-value lands in the borderline range. Real
  experiments do not guarantee this.
- CUPED does not always flip the decision in real experiments.
  This dataset shows the most instructive scenario.
- The activation score is a proxy metric. Real activation scores
  have floor effects (many users at 0) and ceiling effects
  (power users maxing out) that we do not fully simulate.

### Techniques activated
All eight techniques fire on this dataset:
- **Welch's t-test** — continuous outcome, mean test
- **Bayesian** — Normal-Normal model
- **CUPED** — pre_experiment_outcome with r=0.629, 39.6% reduction,
  flips significance decision
- **Sequential** — O'Brien-Fleming boundaries
- **Anomaly detection** — 4 checks, all pass (clean experiment)
- **Novelty detection** — stable, no decay (permanent UI change)
- **HTE** — company_size as strongest modifier
- **Segment discovery** — enterprise vs SMB clusters

---

## Dataset 3: Marketplace Fee Reduction

**File:** `marketplace_fee.csv`
**Experiment type:** Mean (continuous GMV per seller)
**Size:** 10,000 sellers — 4,500 control (45%), 5,500 treatment (55%)
**Duration:** 30 days

### Business context
A marketplace reduces the seller transaction fee from 8% to 5%
to test whether lower fees drive increased GMV (gross merchandise
value) per active seller. The experiment has two problems that
make it untrustworthy.

### Why this experiment is intentionally broken

**Problem 1 — Broken randomization (SRM)**
The split is 4,500 control vs 5,500 treatment — a 45/55 split
instead of 50/50. This happened because larger sellers with higher
GMV heard about the fee reduction through their seller network and
self-selected into the treatment condition. The treatment group
is not comparable to the control group.

SRM detection flags this immediately with chi-squared p < 0.0001.

**Problem 2 — Novelty effect**
When fees drop, sellers immediately rush to list more items.
This creates a temporary spike in activity that fades as sellers
settle into a new equilibrium:
- Days 1-5: +$12 lift (sellers flooding new listings)
- Days 6-14: gradual decay
- Days 15-30: +$4 steady state

The apparent treatment effect (~$7 average) is inflated by both
the novelty spike and the selection bias from SRM. The true
sustainable effect is closer to $4 for a comparable population.

### What this teaches
This is the most important failure-mode demonstration in the
platform. A team without proper validity checks would see:
- Significant result (t-test p < 0.05)
- Positive lift ($7 per seller)
- Conclude: fee reduction works, ship it permanently

With Axiom's checks they see:
- SRM detected: groups are not comparable
- Novelty detected: the spike will fade
- Correct conclusion: run a properly randomized experiment
  before making a permanent pricing decision

### Column definitions

| Column | Type | Range | Description |
|---|---|---|---|
| subject_id | string | mkt_000000–mkt_009999 | Unique seller identifier |
| variant | int | 0 or 1 | 0=control (8% fee), 1=treatment (5% fee) |
| outcome | float | 0–5000 | GMV per seller during experiment ($) |
| seller_tenure_days | float | 1–1825 | Days as active seller, lognormal |
| avg_listing_price | float | 1–500 | Average price of items listed ($) |
| listings_count | float | 0–50 | Items listed last month, Poisson |
| category_id | float | 0–9 | Product category (proxy) |
| pre_experiment_outcome | float | 0–5000 | GMV per seller in prior 30 days ($) |
| experiment_day | int | 1–30 | Day of experiment seller was assigned |

### Distribution choices
- **GMV**: Lognormal base with outliers — most sellers have
  moderate GMV, 3% are power sellers with very high GMV. This
  matches real marketplace distributions where a small number
  of sellers drive disproportionate volume.
- **seller_tenure_days**: Lognormal(mean=4.5, sigma=1.2) —
  marketplace sellers tend to be longer-tenured than typical
  app users. Many have been selling for 1-5 years.
- **Treatment group tenure bias**: Treatment sellers have 20%
  higher tenure on average (selection bias). This is what
  creates the SRM — more experienced sellers self-selected in.

### Techniques activated
All eight techniques fire on this dataset, with important flags:
- **Welch's t-test** — continuous GMV outcome
- **Bayesian** — Normal-Normal model (result flagged as unreliable)
- **CUPED** — pre_experiment_outcome with r~0.7, but result
  untrustworthy due to SRM
- **Sequential** — O'Brien-Fleming boundaries
- **Anomaly detection** — variance instability detected in
  treatment group (power sellers concentrated there due to SRM)
- **Novelty detection** — strong decay pattern detected,
  steady-state estimate lower than observed average
- **HTE** — seller_tenure_days as modifier (but unreliable due to SRM)
- **Segment discovery** — runs but flagged

---

## How to regenerate the data

```bash
# Generate all three datasets and upload to Axiom
python scripts/generate_synthetic_data.py

# Generate only (no upload)
python scripts/generate_synthetic_data.py --save-only

# Upload existing CSVs without regenerating
python scripts/generate_synthetic_data.py --upload-only

# Single experiment
python scripts/generate_synthetic_data.py --experiment saas --upload-only
```

## How to add a new experiment

1. Add a generator function `generate_<name>()` to
   `scripts/generate_synthetic_data.py` following the same
   pattern as the existing three.
2. Add the experiment to the `datasets` dict in `main()`.
3. Add a seed experiment in `backend/migrations/seeds.py`.
4. Document the dataset in this README.

Key design principles for new datasets:
- **Each dataset tells one clear story** — what technique does
  it demonstrate that the others don't?
- **Use realistic distributions** — lognormal for money,
  exponential for tenure, Poisson for counts.
- **Inject realistic noise** — real experiments are messy.
  A perfectly clean result is suspicious.
- **Be honest about limitations** — document what the synthetic
  data cannot capture.
