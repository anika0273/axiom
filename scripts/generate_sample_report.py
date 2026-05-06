"""Generate a sample stakeholder report from the e-commerce checkout dataset.

Runs ML analysis on the dataset, constructs FullAnalysisResult and MLAnalysisSummary,
then calls build_fallback_report (no API key required for the sample).

Usage:
    PYTHONPATH=backend python scripts/generate_sample_report.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import numpy as np
import pandas as pd

from app.intelligence.interpreter import FullAnalysisResult, MLAnalysisSummary
from app.intelligence.reporter import build_fallback_report
from app.ml.engine import MLExperimentInput, run_ml_analysis
from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment


def load_ecommerce_dataset() -> dict:
    data_path = Path(__file__).parent.parent / "backend/app/data/samples/ecommerce_checkout.json"
    with open(data_path) as f:
        return json.load(f)


def run(use_real_claude: bool = False) -> None:
    print("Loading e-commerce checkout dataset...", flush=True)
    dataset = load_ecommerce_dataset()

    metadata = dataset["metadata"]
    user_data = dataset["user_data"]
    daily_data = dataset.get("daily_data", [])

    df = pd.DataFrame(user_data)
    control = df[df["treatment"] == 0]
    treatment = df[df["treatment"] == 1]

    print(f"  Control: {len(control):,} users  Treatment: {len(treatment):,} users")
    print(f"  Baseline conversion: {control['outcome'].mean():.4f}")
    print(f"  Treatment conversion: {treatment['outcome'].mean():.4f}")

    # ── Stats engine ──────────────────────────────────────────────────────
    print("\nRunning stats engine...", flush=True)
    config = ExperimentConfig(
        experiment_id="ecommerce_sample",
        experiment_type="proportion",
        alpha=0.05,
        power=0.80,
        mde=metadata["mde"],
        baseline_rate=metadata["baseline_metric"],
        sequential=False,
        n_looks=1,
    )
    data = ExperimentData(
        control_n=len(control),
        treatment_n=len(treatment),
        control_success=int(control["outcome"].sum()),
        treatment_success=int(treatment["outcome"].sum()),
    )
    stats_analysis = analyze_experiment(config, data)
    primary = stats_analysis.primary_result

    stats_result = FullAnalysisResult(
        is_significant=bool(primary.is_significant),
        p_value=float(primary.p_value),
        lift_pct=float(primary.lift_pct),
        lift_abs=float(primary.lift_abs),
        overall_recommendation=stats_analysis.overall_recommendation,
        warnings=list(stats_analysis.warnings),
        plain_english=stats_analysis.plain_english or "",
    )
    print(f"  is_significant: {stats_result.is_significant}")
    print(f"  lift_pct: {stats_result.lift_pct:+.2f}%")
    print(f"  p_value: {stats_result.p_value:.6f}")

    # ── ML engine ─────────────────────────────────────────────────────────
    print("\nRunning ML engine (this may take ~30s)...", flush=True)
    feature_cols = [c for c in df.columns if c not in ("user_id", "treatment", "outcome")]
    user_features = df[feature_cols].reset_index(drop=True)

    daily_df: pd.DataFrame | None = None
    if daily_data:
        daily_df = pd.DataFrame(daily_data)
        # Ensure required columns exist
        if "control_metric" not in daily_df.columns:
            daily_df = None

    ml_input = MLExperimentInput(
        control_values=control["outcome"].tolist(),
        treatment_values=treatment["outcome"].tolist(),
        user_features=user_features,
        daily_metrics=daily_df,
        feature_names=feature_cols,
    )
    ml_full = run_ml_analysis(ml_input)
    print(f"  ML verdict: {ml_full.overall_verdict}")
    print(f"  Can trust: {ml_full.can_trust_results}")
    print(f"  Key insights: {len(ml_full.key_insights)}")

    # Build MLAnalysisSummary from full result
    anomaly_validity = None
    if ml_full.anomaly_result:
        anomaly_validity = ml_full.anomaly_result.overall_validity

    novelty_pattern = None
    if ml_full.novelty_result:
        novelty_pattern = ml_full.novelty_result.pattern

    hte_top = None
    hte_ate = None
    hte_rec = None
    if ml_full.hte_result:
        hte_top = ml_full.hte_result.top_interactions[0] if ml_full.hte_result.top_interactions else None
        hte_ate = float(ml_full.hte_result.ate)
        hte_rec = ml_full.hte_result.business_recommendation

    responsive_segs = None
    seg_rec = None
    if ml_full.segment_result:
        responsive_segs = list(ml_full.segment_result.responsive_segments)
        seg_rec = ml_full.segment_result.overall_recommendation

    ml_result = MLAnalysisSummary(
        overall_verdict=ml_full.overall_verdict,
        can_trust_results=ml_full.can_trust_results,
        key_insights=ml_full.key_insights,
        recommendation=ml_full.recommendation,
        anomaly_validity=anomaly_validity,
        novelty_pattern=novelty_pattern,
        hte_top_modifier=hte_top,
        hte_ate=hte_ate,
        hte_business_recommendation=hte_rec,
        responsive_segments=responsive_segs,
        segment_recommendation=seg_rec,
    )

    # ── Generate report ───────────────────────────────────────────────────
    print("\nGenerating stakeholder report (fallback mode — no API key needed)...", flush=True)
    report = build_fallback_report(
        experiment_name=metadata["name"],
        stats_result=stats_result,
        ml_result=ml_result,
        daily_traffic=500,
        daily_revenue=50000.0,
    )

    print(f"\n{'='*70}")
    print(report.markdown_content)
    print(f"{'='*70}")
    print(f"\nReport stats:")
    print(f"  Recommendation: {report.recommendation}")
    print(f"  Confidence: {report.confidence_level}")
    print(f"  Key metric: {report.key_metric}")
    print(f"  Word count: {report.word_count}")
    print(f"  Sections: {len(report.sections)}")
    print(f"  AI sections: {len(report.ai_generated_sections)}")
    print(f"  Programmatic sections: {len(report.programmatic_sections)}")

    # Save to file
    out_path = Path(__file__).parent.parent / "docs" / "sample_report_ecommerce.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(report.markdown_content)
    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    run()
