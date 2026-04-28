# scripts

Dev-ops and data management helper scripts. All scripts are standalone and
document their usage with a `--help` flag or top-of-file comment.

Planned scripts:
- `seed_db.py` — Populate the database with realistic sample experiments for local dev
- `run_migrations.sh` — Wrapper around `alembic upgrade head` with safety checks
- `train_lift_model.py` — Train and serialise the XGBoost lift predictor to `ml/artifacts/`
- `backfill_stats.py` — Recompute stats for historical experiments after algorithm changes
