// Sample experiment data for the demo mode and for augmenting live DB experiments.
// The trimmed JSONs (no user_data) live in ./samples/ and are imported here.
// SAMPLE_DATA is keyed by the live DB experiment UUID.
// DEMO_DATA_BY_SLUG is keyed by the route slug used by /demo/:name.

import ecommerceRaw from './samples/ecommerce_checkout.json'
import saasRaw from './samples/saas_trial.json'
import marketplaceRaw from './samples/marketplace_fee.json'

// DB experiment UUIDs (matches what's seeded by backend/migrations/seeds.py)
export const ECOMMERCE_ID = '6d160855-8a47-49c2-9ced-8640a9e2fab2'
export const SAAS_ID = 'f02d296f-6fc4-4dd3-ab79-c919aaf1fee4'
export const MARKETPLACE_ID = '88ef7eea-9ebb-4321-8daf-9dd5b7662158'

/**
 * Convert backend JSON format to the internal sample shape expected by
 * ExperimentResults / DemoExperimentResults. Does NOT normalise CI units —
 * each consumer is responsible for that because the correct conversion
 * depends on whether the experiment is a proportion or mean test.
 */
function fromJSON(raw) {
  const { metadata, daily_data, precomputed_result } = raw
  const { stats_result, ml_result } = precomputed_result

  return {
    controlN: metadata.n_control,
    treatmentN: metadata.n_treatment,
    metadata,
    stats: {
      primary: stats_result.primary_result,
      overall_recommendation: stats_result.overall_recommendation,
      plain_english: stats_result.plain_english,
      warnings: stats_result.warnings ?? [],
      sequential_status: stats_result.sequential_status ?? null,
    },
    ml: ml_result,
    // Map daily_data to { day, date, control, treatment, effect }
    dailyData: daily_data?.length
      ? daily_data.map((d, i) => ({
          day: i + 1,
          date: d.date,
          control: d.control_metric,
          treatment: d.treatment_metric,
          effect: d.treatment_effect,
        }))
      : null,
  }
}

const ECOMMERCE = fromJSON(ecommerceRaw)
const SAAS = fromJSON(saasRaw)
const MARKETPLACE = fromJSON(marketplaceRaw)

// Keyed by DB UUID — used by ExperimentResults to augment live experiments
export const SAMPLE_DATA = {
  [ECOMMERCE_ID]: ECOMMERCE,
  [SAAS_ID]: SAAS,
  [MARKETPLACE_ID]: MARKETPLACE,
}

// Keyed by route slug — used by DemoExperimentResults (/demo/:name)
export const DEMO_DATA_BY_SLUG = {
  ecommerce: ECOMMERCE,
  saas: SAAS,
  marketplace: MARKETPLACE,
}

// Maps demo slug → DB experiment UUID so live AI endpoints can be used
export const DEMO_ID_BY_SLUG = {
  ecommerce: ECOMMERCE_ID,
  saas: SAAS_ID,
  marketplace: MARKETPLACE_ID,
}

// Human-readable labels for the demo gallery
export const DEMO_META = {
  ecommerce: {
    title: 'E-Commerce Checkout',
    slug: 'ecommerce',
    highlights: ['SRM detected', 'Novelty decay', 'Mobile vs Desktop HTE'],
  },
  saas: {
    title: 'SaaS Free Trial',
    slug: 'saas',
    highlights: ['Clean result', 'Stable effect', 'Enterprise segment lift'],
  },
  marketplace: {
    title: 'Marketplace Fee Reduction',
    slug: 'marketplace',
    highlights: ['Not significant', 'Established vs new seller HTE'],
  },
}
