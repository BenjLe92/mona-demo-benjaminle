// Mirrors the backend response models in backend/app/domain and backend/app/api/routes.py.

export type TriState = 'yes' | 'no' | 'unknown'
export type Outcome = 'pass' | 'fail' | 'needs_verification' | 'not_applicable'
export type EligibilityStatus = 'likely_eligible' | 'needs_verification' | 'ineligible'
export type MatchBucket = 'grant' | 'loan' | 'coming_soon'

export interface BusinessSummary {
  profile_id: string
  city: string
  state: string
  industry_label: string | null
  business_type: string | null
  unknown_count: number
}

export interface BusinessProfile {
  profile_id: string
  city: string
  state: string
  state_name: string
  industry_label: string | null
  unmapped_industries: string[]
  years_in_business_label: string | null
  revenue_label: string | null
  credit_score_label: string | null
  employees_label: string | null
  funding_uses: string[]
  funding_timing: string | null
  business_type: string | null
  woman_owned: TriState
  black_owned: TriState
  bipoc_owned: TriState
  veteran_owned: TriState
  nonprofit: TriState
  brick_and_mortar: TriState
  unknown_fields: string[]
}

export interface RuleResult {
  rule: string
  label: string
  outcome: Outcome
  reason: string
  required: string | null
  actual: string | null
}

export interface Eligibility {
  status: EligibilityStatus
  summary: string
  checks: RuleResult[]
  warnings: string[]
}

export interface ScoreComponent {
  name: string
  label: string
  points: number
  max: number
  reason: string
}

export interface Relevance {
  score: number
  summary: string
  components: ScoreComponent[]
}

export interface Amount {
  min: number | null
  max: number | null
  raw: string | null
}

export interface Match {
  opportunity_id: string
  kind: 'grant' | 'loan'
  category: string
  listing_status: 'open' | 'coming_soon'
  name: string
  provider: string | null
  amount: Amount
  deadline: { date: string | null; kind: string; label: string } | null
  url: string
  eligibility: Eligibility
  relevance: Relevance
  details: Record<string, string>
  limitations: string[]
  description: string | null
  criteria_text: string | null
}

export type StatusCounts = Record<EligibilityStatus, number>

export interface MatchResponse {
  profile_id: string
  as_of: string
  counts: Record<MatchBucket, StatusCounts>
  total: number
  results: Match[]
}
