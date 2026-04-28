# stats

Pure statistical functions — no database, no HTTP.

Every public function must:
1. Have full type annotations (input and return)
2. Have a docstring with Args and Returns sections
3. Have a corresponding pytest test in `tests/unit/test_stats_*.py`

Planned modules:
- `frequentist.py` — z-test, t-test, chi-squared, sample size calculation
- `bayesian.py` — Beta-Binomial conjugate updates, credible intervals
- `sequential.py` — Sequential probability ratio test (SPRT), always-valid inference
- `cuped.py` — CUPED variance reduction using pre-experiment covariates
- `utils.py` — Shared helpers (effect size, power, confidence interval formatting)
