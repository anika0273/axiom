# ml

Machine learning models for experiment intelligence.

Every public function must:
1. Have full type annotations
2. Have a docstring
3. Have a unit test in `tests/unit/test_ml_*.py`

Planned modules:
- `lift_predictor.py` — XGBoost model predicting expected metric lift from experiment features
- `outlier_detector.py` — Isolation Forest / statistical outlier detection on metric time-series
- `segment_finder.py` — SHAP-based heterogeneous treatment effect analysis
- `novelty_effect.py` — Detect and model novelty/primacy effects over time

Models are trained offline (scripts in `scripts/`) and serialised to `ml/artifacts/`.
`artifacts/` is excluded from git via `.gitignore`.
