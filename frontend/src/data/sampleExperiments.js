// Precomputed results for the 3 seeded sample experiments.
// Used to populate the Results dashboard because the backend API's
// /experiments/:id endpoint returns a lightweight summary only.
// When the backend stores full analysis in latest_result, this file
// becomes the fallback / demo layer.

export const ECOMMERCE_ID = '6d160855-8a47-49c2-9ced-8640a9e2fab2'
export const SAAS_ID = 'f02d296f-6fc4-4dd3-ab79-c919aaf1fee4'
export const MARKETPLACE_ID = '88ef7eea-9ebb-4321-8daf-9dd5b7662158'

const ECOMMERCE = {
  controlN: 4500,
  treatmentN: 5500,
  stats: {
    primary: {
      is_significant: true,
      p_value: 0.0,
      confidence_interval: [0.10844, 0.13677],
      lift_pct: 119.4215,
      lift_abs: 0.122606,
      test_type: 'z-test',
      sample_warnings: [],
      interpretation:
        'Treatment conversion improved by 119.4% relative (+0.1226 absolute) (p<0.001, significant at α=0.05)',
    },
    overall_recommendation: 'STOP_WIN',
    plain_english:
      'The experiment has a winner. Treatment improved by 119.4% relative (+0.1226 absolute). However, a sample ratio mismatch was detected — verify data integrity before acting.',
    warnings: [
      'Group imbalance detected: control_n=4500, treatment_n=5500 (ratio 0.82). Results may have reduced power.',
    ],
    sequential_status: null,
  },
  ml: {
    overall_verdict: 'INVALID',
    can_trust_results: false,
    recommendation:
      'Do not act on these results. Data integrity issues detected (SRM). Audit assignment pipeline before continuing.',
    key_insights: [
      'Data quality issues detected (srm_check). Validity: INVALID.',
      'Novelty effect detected. Wait 1 days for steady-state.',
      'Strongest treatment modifier: device_type (ATE=+0.1226, stability=0.98). Target top 20% of users by predicted lift (ITE ≥ 0.223).',
    ],
    anomaly: {
      overall_validity: 'INVALID',
      can_trust_results: false,
      recommendation:
        'Do not trust these results. Investigate data pipeline before continuing.',
      checks: [
        {
          name: 'srm_check',
          passed: false,
          score: 2.2e-11,
          severity: 'critical',
          description:
            'SRM detected: observed 54.84% treatment vs expected 50.00% (χ²=44.78, p<0.001). Randomization may be broken.',
          action:
            'Halt experiment analysis. Audit the assignment pipeline for deterministic bucketing bugs, cache poisoning, or bot traffic.',
        },
        {
          name: 'outlier_days',
          passed: true,
          score: 0.0,
          severity: 'info',
          description: 'No anomalous days detected across 21 days.',
          action: 'No action required.',
        },
        {
          name: 'cusum_drift',
          passed: true,
          score: 9.38,
          severity: 'info',
          description:
            'No metric drift detected (max cumsum=9.38, threshold=10.0).',
          action: 'No action required.',
        },
        {
          name: 'volume_spike',
          passed: true,
          score: 0.0,
          severity: 'info',
          description:
            'No volume spikes detected. Baseline mean=514, threshold=641.',
          action: 'No action required.',
        },
      ],
    },
    novelty: {
      pattern: 'NOVELTY',
      slope: -0.009816,
      slope_ci: [-0.01097, -0.00866],
      initial_lift: 0.21206,
      projected_stable_lift: 0.0,
      days_to_stable: 1,
      confidence: 'high',
      recommendation:
        'Novelty effect detected. Wait 1 days for steady-state. Estimated steady-state effect: ~0%.',
    },
    segments: {
      optimal_k: 4,
      silhouette_score: 0.4742,
      responsive_segments: [1, 2, 3],
      overall_recommendation:
        'Roll out to segments 1, 2, 3. Avoid segment 0 (negative lift). Overall ATE: +0.123.',
      low_confidence: false,
      segments: [
        {
          id: 0,
          size_pct: 0.2976,
          lift: -0.0235,
          lift_uncertainty: 0.0,
          description:
            'Mid-sized group (30% of users) with cart_value below average (41.01 vs 49.92). Negative responders.',
          significant: true,
          top_features: { cart_value: [41.0, 49.9], device_type: [0.0, 0.65] },
        },
        {
          id: 1,
          size_pct: 0.5562,
          lift: 0.192295,
          lift_uncertainty: 0.0,
          description:
            'Large group (56% of users) with cart_value below average. Strong positive responders.',
          significant: true,
          top_features: {
            cart_value: [39.7, 49.9],
            n_prior_orders: [0.43, 1.02],
          },
        },
        {
          id: 2,
          size_pct: 0.1021,
          lift: 0.125882,
          lift_uncertainty: 0.0,
          description:
            'Small group (10% of users) with user_age_days well above average (110 vs 37). Loyal users.',
          significant: true,
          top_features: { user_age_days: [110.5, 36.8], cart_value: [61.6, 49.9] },
        },
        {
          id: 3,
          size_pct: 0.0441,
          lift: 0.230416,
          lift_uncertainty: 0.0,
          description:
            'Small high-value group (4% of users) with cart_value well above average (211 vs 50). Highest lift.',
          significant: true,
          top_features: { cart_value: [211.3, 49.9], n_prior_orders: [1.42, 1.02] },
        },
      ],
    },
    hte: {
      ate: 0.122606,
      stability_score: 0.9797,
      business_recommendation:
        'Target top 20% of users by predicted lift (ITE ≥ 0.223); expected lift for this segment: +0.270 driven by device_type. Overall ATE: +0.123.',
      ite_uncertainty_mean: 0.0,
      top_interactions: ['device_type_x_treat', 'cart_value_x_treat'],
    },
  },
  dailyData: [
    { day: 1, date: '2026-03-02', control: 0.1003, treatment: 0.2996, effect: 0.1993 },
    { day: 2, date: '2026-03-03', control: 0.0984, treatment: 0.3018, effect: 0.2034 },
    { day: 3, date: '2026-03-04', control: 0.0982, treatment: 0.3021, effect: 0.2039 },
    { day: 4, date: '2026-03-05', control: 0.1000, treatment: 0.3007, effect: 0.2007 },
    { day: 5, date: '2026-03-06', control: 0.0943, treatment: 0.2773, effect: 0.1830 },
    { day: 6, date: '2026-03-07', control: 0.1012, treatment: 0.2712, effect: 0.1700 },
    { day: 7, date: '2026-03-08', control: 0.0998, treatment: 0.2543, effect: 0.1545 },
    { day: 8, date: '2026-03-09', control: 0.1008, treatment: 0.2412, effect: 0.1404 },
    { day: 9, date: '2026-03-10', control: 0.0987, treatment: 0.2287, effect: 0.1300 },
    { day: 10, date: '2026-03-11', control: 0.0995, treatment: 0.2198, effect: 0.1203 },
    { day: 11, date: '2026-03-12', control: 0.1005, treatment: 0.2105, effect: 0.1100 },
    { day: 12, date: '2026-03-13', control: 0.1002, treatment: 0.2012, effect: 0.1010 },
    { day: 13, date: '2026-03-14', control: 0.0998, treatment: 0.1945, effect: 0.0947 },
    { day: 14, date: '2026-03-15', control: 0.1001, treatment: 0.1889, effect: 0.0888 },
    { day: 15, date: '2026-03-16', control: 0.1003, treatment: 0.1832, effect: 0.0829 },
    { day: 16, date: '2026-03-17', control: 0.1001, treatment: 0.1781, effect: 0.0780 },
    { day: 17, date: '2026-03-18', control: 0.0996, treatment: 0.1742, effect: 0.0746 },
    { day: 18, date: '2026-03-19', control: 0.0998, treatment: 0.1710, effect: 0.0712 },
    { day: 19, date: '2026-03-20', control: 0.1000, treatment: 0.1680, effect: 0.0680 },
    { day: 20, date: '2026-03-21', control: 0.1002, treatment: 0.1652, effect: 0.0650 },
    { day: 21, date: '2026-03-22', control: 0.0999, treatment: 0.1625, effect: 0.0626 },
  ],
}

const SAAS = {
  controlN: 5000,
  treatmentN: 5000,
  stats: {
    primary: {
      is_significant: true,
      p_value: 0.0012,
      confidence_interval: [0.018, 0.042],
      lift_pct: 25.0,
      lift_abs: 0.03,
      test_type: 'z-test',
      sample_warnings: [],
      interpretation:
        'Treatment trial-to-paid conversion improved by 25.0% relative (+0.03 absolute) (p=0.001, significant at α=0.05)',
    },
    overall_recommendation: 'STOP_WIN',
    plain_english:
      'Extending the free trial to 30 days produced a significant lift in trial-to-paid conversion, especially for larger companies.',
    warnings: [],
    sequential_status: null,
  },
  ml: {
    overall_verdict: 'CLEAN',
    can_trust_results: true,
    recommendation:
      'Roll out to all users, prioritising enterprise segments where lift is highest.',
    key_insights: [
      'Results are clean — no data integrity issues detected.',
      'Effect is heterogeneous: enterprise companies (>50 seats) show +45% relative lift vs +12% for small teams.',
    ],
    anomaly: {
      overall_validity: 'CLEAN',
      can_trust_results: true,
      recommendation: 'Results are valid. Proceed with analysis.',
      checks: [
        {
          name: 'srm_check',
          passed: true,
          score: 0.87,
          severity: 'info',
          description: 'No SRM detected (p=0.87). Assignment ratios are balanced.',
          action: 'No action required.',
        },
      ],
    },
    novelty: {
      pattern: 'STABLE',
      slope: 0.0002,
      slope_ci: [-0.001, 0.0014],
      initial_lift: 0.031,
      projected_stable_lift: 0.03,
      days_to_stable: 0,
      confidence: 'high',
      recommendation: 'Effect is stable. No novelty decay detected.',
    },
    segments: null,
    hte: {
      ate: 0.03,
      stability_score: 0.94,
      business_recommendation:
        'Enterprise segment (company_size > 50) shows 2x the average lift. Prioritise rollout there.',
      ite_uncertainty_mean: 0.004,
      top_interactions: ['company_size_x_treat', 'plan_tier_x_treat'],
    },
  },
  dailyData: null,
}

const MARKETPLACE = {
  controlN: 4800,
  treatmentN: 4800,
  stats: {
    primary: {
      is_significant: false,
      p_value: 0.214,
      confidence_interval: [-0.018, 0.074],
      lift_pct: 8.1,
      lift_abs: 0.0202,
      test_type: 't-test',
      sample_warnings: [],
      interpretation:
        'Treatment GMV improved by 8.1% relative (+$20.2 average) but the result is not statistically significant (p=0.21).',
    },
    overall_recommendation: 'CONTINUE',
    plain_english:
      'The fee reduction shows a positive but non-significant effect on GMV. More data needed.',
    warnings: [],
    sequential_status: null,
  },
  ml: {
    overall_verdict: 'NEEDS_REVIEW',
    can_trust_results: true,
    recommendation:
      'Continue the experiment or run a pre-registered power analysis. Effect is promising but underpowered.',
    key_insights: [
      'Results are valid but not yet significant.',
      'Established sellers (>12 months) show a significant positive effect. New sellers show a slight decline.',
    ],
    anomaly: {
      overall_validity: 'CLEAN',
      can_trust_results: true,
      recommendation: 'No data integrity issues detected.',
      checks: [
        {
          name: 'srm_check',
          passed: true,
          score: 0.62,
          severity: 'info',
          description: 'No SRM detected.',
          action: 'No action required.',
        },
      ],
    },
    novelty: null,
    segments: null,
    hte: {
      ate: 0.0202,
      stability_score: 0.78,
      business_recommendation:
        'Effect is driven by established sellers (>12 months tenure). Consider targeting the rollout.',
      ite_uncertainty_mean: 0.012,
      top_interactions: ['seller_tenure_x_treat'],
    },
  },
  dailyData: null,
}

export const SAMPLE_DATA = {
  [ECOMMERCE_ID]: ECOMMERCE,
  [SAAS_ID]: SAAS,
  [MARKETPLACE_ID]: MARKETPLACE,
}
