Run a live demo of the Axiom stats engine using a realistic shopping A/B test scenario.

Execute this Python demo from the project root:

```bash
cd /Users/owner/Desktop/Test_claude && python -c "
import sys
sys.path.insert(0, 'backend')

import numpy as np
from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment

rng = np.random.default_rng(42)
n = 5000

# Pre-period revenue as CUPED covariate (correlation ~0.6 with post-period)
pre = rng.normal(10.0, 5.0, 2 * n)
noise = rng.normal(0, 4.0, 2 * n)
post = 0.6 * pre + noise
post[n:] += 0.3  # +0.3 revenue lift in treatment (not used directly in proportion test)

config = ExperimentConfig(
    alpha=0.05,
    power=0.80,
    test_type='proportion',
    sequential_looks=2,
    n_metrics=3,
    has_cuped_data=True,
    planned_n_per_group=5000,
)
data = ExperimentData(
    control_n=n,
    treatment_n=n,
    control_success=250,    # 5.0% baseline conversion
    treatment_success=325,  # 6.5% treatment conversion (+30% relative lift)
    cuped_covariates=pre.tolist(),
)

result = analyze_experiment(config, data, current_look=2)

sep = '=' * 60
print(sep)
print('  AXIOM STATS ENGINE — DEMO OUTPUT')
print(sep)
print(f'  Scenario : Shopping conversion, n={n:,}/group')
print(f'  Control  : {data.control_success}/{n} = 5.00%')
print(f'  Treatment: {data.treatment_success}/{n} = 6.50%  (+30% relative)')
print(sep)
print()

print('[ POWER ANALYSIS ]')
ss = result.required_sample_size
print(f'  Required n/group : {ss.control_size:,}')
print(f'  Total required n : {ss.total_sample_size:,}')
print(f\"  Cohen's d        : {ss.cohens_d:.4f}\")
print(f'  Method           : {ss.method_used}')
print()

print('[ PRIMARY TEST (z-test) ]')
pr = result.primary_result
print(f'  p-value          : {pr.p_value:.6f}')
print(f'  Test statistic   : {pr.test_statistic:.4f}')
print(f'  Significant      : {pr.is_significant}')
print(f'  Lift (relative)  : {pr.lift_pct:+.2f}%')
print(f'  Lift (absolute)  : {pr.lift_abs:+.4f}')
ci_lo, ci_hi = pr.confidence_interval
print(f'  95% CI           : [{ci_lo:+.4f}, {ci_hi:+.4f}]')
print()

print('[ SEQUENTIAL ANALYSIS ]')
if result.sequential_status:
    sq = result.sequential_status
    print(f'  Decision         : {sq.decision}')
    print(f'  Info fraction    : {sq.info_fraction_complete:.2%}')
    print(f'  Current |z|      : {abs(sq.current_z):.4f}')
    print(f'  O-B-F boundary   : {sq.required_z:.4f}')
else:
    print('  (disabled)')
print()

print('[ CUPED ]')
if result.cuped_result:
    cu = result.cuped_result
    print(f'  Variance reduction: {cu.variance_reduction_pct:.1f}%')
    print(f'  Pre-post corr (r) : {cu.correlation_pre_post:.4f}')
    print(f'  theta             : {cu.theta:.4f}')
    adj = cu.adjusted_test_result
    print(f'  Adjusted p-value  : {adj.p_value:.6f}')
    print(f'  Adjusted |z|      : {abs(adj.test_statistic):.4f}')
    print(f'  Recommendation    : {cu.recommendation}')
else:
    print('  (disabled)')
print()

print('[ CORRECTIONS (BH FDR) ]')
if result.corrected_results:
    cr = result.corrected_results
    print(f'  Method           : {cr.method}')
    print(f'  Original p       : {list(cr.original_p.round(6))}')
    print(f'  Corrected p      : {list(cr.corrected_p.round(6))}')
    print(f'  Rejected         : {list(cr.reject_mask)}')
    print(f'  n_rejected       : {cr.n_rejected}')
else:
    print('  (disabled)')
print()

print('[ OVERALL RECOMMENDATION ]')
print(f'  Decision         : {result.overall_recommendation}')
print()
print('  Plain English:')
for line in result.plain_english.split('. '):
    if line.strip():
        print(f'    {line.strip()}.')
print()

if result.warnings:
    print('[ WARNINGS ]')
    for w in result.warnings:
        print(f'  ⚠  {w}')
    print()

print(sep)
" 2>&1
```

Display the complete formatted output exactly as produced. If any import or runtime error occurs, show the full traceback and explain the fix needed.
