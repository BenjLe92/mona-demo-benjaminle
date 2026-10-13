import { fireEvent, render, screen } from '@testing-library/react'
import { formatAmount } from '../format'
import type { EligibilityStatus, Match } from '../types/api'
import { EligibilityChecklist } from './EligibilityChecklist'
import { MatchCard } from './MatchCard'
import { ScoreBreakdown } from './ScoreBreakdown'

function makeMatch(overrides: Partial<Match> = {}): Match {
  return {
    opportunity_id: 'G-0001',
    kind: 'grant',
    category: 'grant',
    listing_status: 'open',
    name: 'Chicago Women Grant',
    provider: null,
    amount: { min: null, max: 5000, raw: 'up to $5,000' },
    deadline: { date: '2026-11-15', kind: 'fixed', label: 'Nov 15, 2026' },
    url: 'https://example.org/grant',
    eligibility: {
      status: 'needs_verification',
      summary: 'Needs verification: ownership: woman-owned.',
      checks: [
        { rule: 'location', label: 'Location', outcome: 'pass', reason: 'Open to businesses in Chicago, IL.', required: 'IL (Chicago)', actual: 'Chicago, IL' },
        { rule: 'founder_requirement', label: 'Ownership: woman-owned', outcome: 'needs_verification', reason: 'Requires a woman-owned business; this is not on file for your profile.', required: 'woman-owned', actual: 'not on file' },
      ],
      warnings: ['Read the full criteria before applying.'],
    },
    relevance: {
      score: 62,
      summary: 'Local to Chicago; fewer businesses can apply.',
      components: [
        { name: 'industry_fit', label: 'Industry fit', points: 15, max: 35, reason: 'Open to all industries.' },
        { name: 'local_fit', label: 'Local fit', points: 20, max: 20, reason: 'Local to Chicago; fewer businesses can apply.' },
      ],
    },
    details: { Location: 'IL (Chicago)' },
    limitations: [],
    description: 'For Chicago founders.',
    criteria_text: 'Must be at least 51% woman-owned.',
    ...overrides,
  }
}

describe('MatchCard', () => {
  it('shows status, score and both explanations without expanding', () => {
    render(<MatchCard match={makeMatch()} />)
    expect(screen.getByRole('heading', { name: 'Chicago Women Grant' })).toBeInTheDocument()
    expect(screen.getByText('Needs Verification')).toBeInTheDocument()
    expect(screen.getByText('62')).toBeInTheDocument()
    expect(screen.getByText('Needs verification: ownership: woman-owned.')).toBeInTheDocument()
    expect(screen.getByText('Local to Chicago; fewer businesses can apply.')).toBeInTheDocument()
    expect(screen.getByText(/up to \$5,000 · Nov 15, 2026/)).toBeInTheDocument()
    expect(screen.queryByText('Eligibility checks')).not.toBeInTheDocument()
  })

  it('reveals checks, score breakdown and full criteria when expanded', () => {
    render(<MatchCard match={makeMatch()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Show details' }))
    expect(screen.getByText('Eligibility checks')).toBeInTheDocument()
    expect(screen.getByText('Relevance: 62 out of 100')).toBeInTheDocument()
    expect(screen.getByText('Must be at least 51% woman-owned.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hide details' })).toHaveAttribute('aria-expanded', 'true')
  })

  it.each<[EligibilityStatus, string]>([
    ['likely_eligible', 'Likely Eligible'],
    ['needs_verification', 'Needs Verification'],
    ['ineligible', 'Ineligible'],
  ])('labels status %s as %s', (status, label) => {
    const match = makeMatch()
    render(<MatchCard match={{ ...match, eligibility: { ...match.eligibility, status } }} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('never labels a match as plainly "Eligible"', () => {
    const match = makeMatch()
    render(<MatchCard match={{ ...match, eligibility: { ...match.eligibility, status: 'likely_eligible' } }} />)
    expect(screen.queryByText('Eligible')).not.toBeInTheDocument()
  })

  it('links loans to the lender and omits the deadline', () => {
    render(<MatchCard match={makeMatch({ kind: 'loan', category: 'loan', name: 'Kiva', deadline: null })} />)
    expect(screen.getByRole('link', { name: 'Go to lender' })).toHaveAttribute('href', 'https://example.org/grant')
    expect(screen.queryByText(/Nov 15/)).not.toBeInTheDocument()
  })
})

describe('EligibilityChecklist', () => {
  it('renders every check with its outcome and reason, plus warnings', () => {
    render(<EligibilityChecklist eligibility={makeMatch().eligibility} />)
    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Verify')).toBeInTheDocument()
    expect(screen.getByText('Open to businesses in Chicago, IL.')).toBeInTheDocument()
    expect(screen.getByText(/this is not on file for your profile/)).toBeInTheDocument()
    expect(screen.getByLabelText('Verification warnings')).toHaveTextContent('Read the full criteria before applying.')
  })

  it('marks a failed requirement as not met', () => {
    const eligibility = makeMatch().eligibility
    const failed = { ...eligibility.checks[0], outcome: 'fail' as const, reason: 'Not available in Illinois (NY).' }
    render(<EligibilityChecklist eligibility={{ ...eligibility, checks: [failed], warnings: [] }} />)
    expect(screen.getByText('Not met')).toBeInTheDocument()
    expect(screen.queryByLabelText('Verification warnings')).not.toBeInTheDocument()
  })
})

describe('ScoreBreakdown', () => {
  it('shows points, maximum and reason for each component', () => {
    render(<ScoreBreakdown relevance={makeMatch().relevance} />)
    expect(screen.getByText('15 / 35')).toBeInTheDocument()
    expect(screen.getByText('20 / 20')).toBeInTheDocument()
    expect(screen.getByText('Open to all industries.')).toBeInTheDocument()
  })
})

describe('formatAmount', () => {
  it('prefers the listing wording and falls back to a formatted range', () => {
    expect(formatAmount({ min: null, max: 5000, raw: 'up to $5,000' })).toBe('up to $5,000')
    expect(formatAmount({ min: 1000, max: 15000, raw: null })).toBe('$1,000 - $15,000')
    expect(formatAmount({ min: null, max: 5000, raw: null })).toBe('up to $5,000')
    expect(formatAmount({ min: null, max: null, raw: null })).toBe('Amount not listed')
  })
})
