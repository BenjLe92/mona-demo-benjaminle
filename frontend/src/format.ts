import type { Amount, EligibilityStatus, Outcome } from './types/api'

export const STATUS_LABELS: Record<EligibilityStatus, string> = {
  likely_eligible: 'Likely Eligible',
  needs_verification: 'Needs Verification',
  ineligible: 'Ineligible',
}

export const OUTCOME_LABELS: Record<Outcome, string> = {
  pass: 'Pass',
  fail: 'Not met',
  needs_verification: 'Verify',
  not_applicable: 'No requirement',
}

const CATEGORY_LABELS: Record<string, string> = {
  grant: 'Grant',
  cash_award: 'Cash award',
  pitch_competition: 'Pitch competition',
  loan: 'Loan',
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}

/** The dataset's own wording when there is one; otherwise a formatted range. */
export function formatAmount(amount: Amount): string {
  if (amount.raw) return amount.raw
  const money = (value: number) => `$${value.toLocaleString('en-US')}`
  if (amount.min != null && amount.max != null) {
    return amount.min === amount.max ? money(amount.max) : `${money(amount.min)} - ${money(amount.max)}`
  }
  if (amount.max != null) return `up to ${money(amount.max)}`
  return 'Amount not listed'
}
