# Axiom — A/B Testing & Experimentation Platform

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-759%20passing-22c55e)
![Coverage](https://img.shields.io/badge/Coverage-85%25-22c55e)
![License](https://img.shields.io/badge/License-MIT-6366f1)

**[GitHub](https://github.com/anika0273/axiom)** · **[Live Demo](https://axiom-gamma-cyan.vercel.app)**

---

## What this is

Axiom is a full-stack A/B testing platform built as a senior 
data science portfolio project. It answers three questions 
for every experiment:

1. **Can we trust this experiment?** — Was the randomization 
   clean? Is the data quality sufficient?
2. **Did the change work?** — Is the result statistically real, 
   not noise?
3. **Who did it work for?** — Does the average lift hide a 
   better or worse story for specific user segments?

Every technique is explained in plain English alongside the 
result — not just the number, but why this technique exists, 
what it found, and what it means for the business decision.

---

## The three experiment stories

Each demo experiment is designed to demonstrate different 
failure modes and techniques:

### E-Commerce Checkout Redesign
*A clean experiment with a significant result that hides a 
mobile/desktop story*

A simplified single-page checkout increases overall conversion 
by +2.7pp (significant, p<0.001). But the average conceals 
that mobile users convert +5pp better while desktop users 
barely move (+0.5pp). The right decision isn't just "ship" — 
it's "ship to mobile first, redesign the desktop version."

Techniques: z-test, Bayesian, power analysis, SRM detection, 
sequential testing, anomaly detection, novelty detection, 
HTE (XGBoost+SHAP), K-means segments

### SaaS Onboarding Checklist
*A borderline result where variance reduction changes the 
business decision*

The standard frequentist test says NOT significant (p=0.775). 
CUPED — using each user's 30-day pre-experiment activation 
score as a covariate — reduces variance by 39.6% and reveals 
the same effect is actually significant (p=0.034). Without 
CUPED, the team would not ship a feature that genuinely works.

Techniques: Welch's t-test, Bayesian, CUPED (changes 
decision), sequential testing, anomaly detection, novelty 
detection (stable), HTE (enterprise vs SMB), segments

### Marketplace Fee Reduction
*A broken experiment that looks like a win*

The experiment shows a positive GMV lift and a significant 
result. But two problems make it untrustworthy: Sample Ratio 
Mismatch (55/45 split instead of 50/50 — larger sellers 
self-selected into treatment) and a strong novelty effect 
(sellers rushed to list items when fees dropped, creating a 
temporary spike). The correct decision is to run a properly 
randomized experiment before making a permanent pricing change.

Techniques: Welch's t-test, Bayesian, SRM detection (FAILS), 
anomaly detection (variance instability), novelty detection 
(strong decay), HTE, segments

---

## Full technique inventory

### Stats engine

| Technique | What it answers | When it activates |
|---|---|---|
| Z-test | Did conversion rate change? | Binary outcome (proportion experiment) |
| Welch's t-test | Did the average change? | Continuous outcome (mean experiment) |
| Bayesian A/B | What's the probability treatment is better? | Always — runs alongside frequentist |
| Power analysis | Did you have enough users? | Always |
| CUPED | Can we be more precise? | When pre_experiment_outcome column present |
| Sequential testing | Could we have stopped earlier? | When experiment_day column present, ≥7 days |
| BH correction | Are we testing too many metrics? | When multiple metrics tested simultaneously |
| SRM detection | Was the randomization clean? | Always |

### ML engine

| Technique | What it finds | When it activates |
|---|---|---|
| XGBoost HTE | Which users respond differently? | When feature columns present |
| SHAP importance | What drives the heterogeneity? | With HTE |
| K-means segments | What natural user groups exist? | When feature columns present |
| Jaccard stability | Are the segments reproducible? | With segments |
| Anomaly detection | Is the daily data behaving normally? | When experiment_day column present |
| Novelty detection | Is the effect fading over time? | When experiment_day column present, ≥7 days |

### What activates each technique

Axiom automatically detects which techniques to run based 
on what columns you upload:

```
Required (always):
subject_id, variant (0/1), outcome

Enables CUPED:
pre_experiment_outcome  — continuous covariate from before
                          the experiment started

Enables sequential + anomaly + novelty:
experiment_day          — which day (1, 2, 3...) each user
                          was assigned

Enables HTE + segments:
Any additional numeric columns  — device_type, company_size,
                                  tenure, etc.
```

---

## What this is not

**Not a causal inference tool for non-randomized data.**
Axiom requires random assignment. For observational data 
(DiD, RDD, propensity matching), different methods are 
needed. Axiom explains this when it's relevant.

**Not a feature flag system.**
Axiom analyzes experiment results — it doesn't handle 
assignment or event tracking. It consumes data you've 
already collected.

**Not autonomous.**
All AI-generated recommendations require human confirmation. 
Axiom is advisory, not decisional.

---

## Architecture

```
Browser
│
▼
React 18 + Vite (frontend)
│  CSV upload → client-side validation (papaparse)
│  Five-act narrative → plain English for every technique
│
▼
FastAPI (Python 3.12)
│
├── Stats pipeline
│     z-test / t-test → CUPED → Bayesian → Sequential
│     → BH correction → SRM → power analysis
│
├── ML pipeline
│     Anomaly detection → Novelty detection
│     → HTE (XGBoost+SHAP) → Segments (K-means+Jaccard)
│
└── PostgreSQL 15
      experiments, experiment_metrics,
      experiment_subjects (JSONB covariates),
      experiment_results
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, SQLAlchemy async, Alembic |
| Statistics | scipy, statsmodels, numpy |
| ML | XGBoost, SHAP, scikit-learn |
| AI | Anthropic SDK (Claude) — optional, for plain-English interpretation |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Database | PostgreSQL 15 |
| Infrastructure | Docker Compose, GitHub Actions CI |

---

## Synthetic datasets

Three independent datasets, each designed to tell a different 
story. See [data/README.md](data/README.md) for full 
documentation of design decisions, distribution choices, 
and honest limitations of synthetic vs real data.

The platform also runs on the 
[Criteo Uplift Modeling Dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) 
— 50,000 real subjects, 12 anonymized behavioral features, 
validated HTE results.

---

## Quick start

```bash
git clone https://github.com/anika0273/axiom.git
cd axiom

cp .env.example .env
# Add ANTHROPIC_API_KEY (optional — platform works without it)
# Add a random SECRET_KEY

docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python backend/migrations/seeds.py

# Generate and upload synthetic data
python scripts/generate_synthetic_data.py

open http://localhost:3000
```

Then open any experiment → hit Recompute → see the full 
analysis with all techniques explained.

---

## Running tests

```bash
# All backend tests (excludes AI tests which need API credits)
docker compose exec backend python -m pytest backend/tests/ \
  --ignore=backend/tests/intelligence/ \
  --ignore=backend/tests/integration/test_intelligence.py \
  -q

# Stats engine only
docker compose exec backend python -m pytest \
  backend/tests/stats/ backend/tests/unit/ -q

# Frontend
cd frontend && npm run test
```

759 tests passing. 85% overall coverage.

---

## What I built and why

This project started as a way to learn experimentation 
deeply — not just implement the formulas, but understand 
why each technique exists, what problem it solves, and 
when it changes a business decision.

The CUPED implementation is the clearest example: it's 
easy to copy the formula. It's harder to understand that 
binary pre-covariates don't work (correlation ceiling), 
that the variance reduction only helps if the covariate 
actually predicts the outcome, and that a 39.6% variance 
reduction can flip a NOT significant result to significant 
— changing whether a feature ships or gets abandoned.

Every technique in this platform has that kind of story 
behind it. The goal was to build something where those 
stories are visible, not hidden in code.

---

## License

MIT
