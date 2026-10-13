import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import type { BusinessProfile, BusinessSummary, EligibilityStatus, Match, MatchResponse } from './types/api'

// --- A small fake of the backend, driven through `fetch` ---------------------------

const BUSINESSES: BusinessSummary[] = ['MONA-0001', 'MONA-0002'].map((profile_id) => ({
  profile_id,
  city: 'Chicago',
  state: 'IL',
  industry_label: 'Retail',
  business_type: null,
  unknown_count: 0,
}))

function makeProfile(profile_id: string): BusinessProfile {
  return {
    profile_id,
    city: 'Chicago',
    state: 'IL',
    state_name: 'Illinois',
    industry_label: 'Retail',
    unmapped_industries: [],
    years_in_business_label: '2-3 years',
    revenue_label: '$100,000 - $249,999',
    credit_score_label: '680 - 719',
    employees_label: '1 employee',
    funding_uses: ['Inventory'],
    funding_timing: 'Within a month',
    business_type: 'Sole Proprietor',
    woman_owned: 'yes',
    black_owned: 'no',
    bipoc_owned: 'no',
    veteran_owned: 'no',
    nonprofit: 'no',
    brick_and_mortar: 'yes',
    unknown_fields: [],
  }
}

function makeMatch(index: number, kind: 'grant' | 'loan'): Match {
  const status: EligibilityStatus = 'needs_verification'
  return {
    opportunity_id: `${kind}-${index}`,
    kind,
    category: kind,
    listing_status: 'open',
    name: `${kind === 'grant' ? 'Grant' : 'Loan'} ${index}`,
    provider: null,
    amount: { min: null, max: 5000, raw: 'up to $5,000' },
    deadline: null,
    url: 'https://example.org',
    eligibility: { status, summary: 'Passed: location. To verify: other stated criteria.', checks: [], warnings: [] },
    relevance: { score: 50, summary: 'Open to all industries.', components: [] },
    details: {},
    limitations: [],
    description: null,
    criteria_text: null,
  }
}

const GRANTS = Array.from({ length: 130 }, (_, i) => makeMatch(i + 1, 'grant'))
const LOANS = Array.from({ length: 3 }, (_, i) => makeMatch(i + 1, 'loan'))

function matchResponse(url: URL): MatchResponse {
  const all = url.searchParams.get('kind') === 'loan' ? LOANS : GRANTS
  const offset = Number(url.searchParams.get('offset') ?? 0)
  const limit = Number(url.searchParams.get('limit') ?? 25)
  const zero = { likely_eligible: 0, needs_verification: 0, ineligible: 0 }
  return {
    profile_id: url.pathname.split('/')[3],
    as_of: '2026-10-13',
    counts: {
      grant: { ...zero, needs_verification: GRANTS.length },
      loan: { ...zero, needs_verification: LOANS.length },
      coming_soon: zero,
    },
    total: all.length,
    results: all.slice(offset, offset + limit),
  }
}

type Gate = { promise: Promise<void>; open: () => void }
function gate(): Gate {
  let open = () => {}
  const promise = new Promise<void>((resolve) => (open = resolve))
  return { promise, open }
}

/** Per-test switches: fail a kind of request, or hold it until a gate opens. */
const api = {
  failing: new Set<'list' | 'profile' | 'matches'>(),
  held: new Map<'list' | 'profile' | 'matches', Gate>(),
  requests: [] as string[],
}

function kindOf(url: URL): 'list' | 'profile' | 'matches' {
  if (url.pathname.endsWith('/matches')) return 'matches'
  return url.pathname === '/api/businesses' ? 'list' : 'profile'
}

beforeEach(() => {
  api.failing.clear()
  api.held.clear()
  api.requests = []
  vi.stubGlobal('fetch', async (input: string) => {
    const url = new URL(input, 'http://localhost')
    const kind = kindOf(url)
    api.requests.push(url.pathname + url.search)
    await api.held.get(kind)?.promise
    if (api.failing.has(kind)) {
      return new Response(JSON.stringify({ detail: `${kind} request failed` }), { status: 500 })
    }
    const body =
      kind === 'list' ? BUSINESSES : kind === 'profile' ? makeProfile(url.pathname.split('/')[3]) : matchResponse(url)
    return new Response(JSON.stringify(body), { status: 200 })
  })
})

afterEach(() => vi.unstubAllGlobals())

const cards = () => screen.queryAllByRole('article')
const pick = async (id: string) => fireEvent.click(await screen.findByRole('button', { name: new RegExp(id) }))

// --- Pagination ------------------------------------------------------------------------

describe('pagination', () => {
  it('reaches every result, past the first 100, by requesting further pages', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))

    for (const shown of [50, 75, 100, 125]) {
      fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
      await waitFor(() => expect(cards()).toHaveLength(shown))
      expect(screen.getByRole('button', { name: `Show more (${shown} of 130)` })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    await waitFor(() => expect(cards()).toHaveLength(130))

    expect(screen.queryByRole('button', { name: /Show more/ })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Grant 1' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Grant 130' })).toBeInTheDocument()
    const names = cards().map((card) => within(card).getByRole('heading').textContent)
    expect(new Set(names).size).toBe(130) // no page was fetched twice
  })

  it('asks the API for one page at a time using offset', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    await waitFor(() => expect(cards()).toHaveLength(50))

    const matchRequests = api.requests.filter((r) => r.includes('/matches'))
    expect(matchRequests.at(-1)).toContain('limit=25')
    expect(matchRequests.at(-1)).toContain('offset=25')
    expect(matchRequests.every((r) => r.includes('limit=25'))).toBe(true)
  })

  it('starts again from the first page when the tab changes', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    await waitFor(() => expect(cards()).toHaveLength(50))

    fireEvent.click(screen.getByRole('tab', { name: /Loans/ }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Loan 1' })).toBeInTheDocument())
    expect(cards()).toHaveLength(3)
    expect(api.requests.at(-1)).toContain('offset=0')
  })

  it('keeps the loaded cards and allows a retry when a later page fails', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))

    api.failing.add('matches')
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('matches request failed')
    expect(cards()).toHaveLength(25)

    api.failing.clear()
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    await waitFor(() => expect(cards()).toHaveLength(50))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

// --- Error recovery ----------------------------------------------------------------------

describe('error recovery', () => {
  it('clears a profile error once another business loads', async () => {
    render(<App />)
    api.failing.add('profile')
    await pick('MONA-0001')
    expect(await screen.findByRole('alert')).toHaveTextContent('profile request failed')

    api.failing.clear()
    await pick('MONA-0002')
    expect(await screen.findByRole('heading', { name: /MONA-0002/ })).toBeInTheDocument()
    await waitFor(() => expect(cards()).toHaveLength(25))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('retries when the same business is picked again after a failure', async () => {
    render(<App />)
    api.failing.add('profile')
    await pick('MONA-0001')
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    api.failing.clear()
    await pick('MONA-0001')
    expect(await screen.findByRole('heading', { name: /MONA-0001/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('clears a matches error when the next request succeeds', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))

    api.failing.add('matches')
    fireEvent.click(screen.getByRole('tab', { name: /Loans/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('matches request failed')
    expect(cards()).toHaveLength(0) // grants are not left on screen under the Loans tab

    api.failing.clear()
    fireEvent.click(screen.getByRole('tab', { name: /Grants/ }))
    await waitFor(() => expect(cards()).toHaveLength(25))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reports a failed business list', async () => {
    api.failing.add('list')
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('list request failed')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

// --- Loading states ----------------------------------------------------------------------

describe('loading feedback', () => {
  it('shows a status while the business list loads', async () => {
    const hold = gate()
    api.held.set('list', hold)
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading businesses…')
    hold.open()
    await screen.findByRole('button', { name: /MONA-0001/ })
    expect(screen.queryByText('Loading businesses…')).not.toBeInTheDocument()
  })

  it('shows a status while a business profile loads', async () => {
    render(<App />)
    const hold = gate()
    api.held.set('profile', hold)
    await pick('MONA-0001')
    expect(await screen.findByText('Loading business profile…')).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('heading', { name: /MONA-0001/ })).not.toBeInTheDocument()

    hold.open()
    expect(await screen.findByRole('heading', { name: /MONA-0001/ })).toBeInTheDocument()
    expect(screen.queryByText('Loading business profile…')).not.toBeInTheDocument()
  })

  it('shows a status while switching to another business, not the previous profile', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))

    const hold = gate()
    api.held.set('profile', hold)
    await pick('MONA-0002')
    expect(await screen.findByText('Loading business profile…')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /MONA-0001/ })).not.toBeInTheDocument()
    hold.open()
    expect(await screen.findByRole('heading', { name: /MONA-0002/ })).toBeInTheDocument()
  })

  it('shows a status while the first matches load', async () => {
    render(<App />)
    const hold = gate()
    api.held.set('matches', hold)
    await pick('MONA-0001')
    expect(await screen.findByText('Loading matches…')).toHaveAttribute('role', 'status')
    hold.open()
    await waitFor(() => expect(cards()).toHaveLength(25))
    expect(screen.queryByText('Loading matches…')).not.toBeInTheDocument()
  })

  it('shows a status when the tab changes and while a further page loads', async () => {
    render(<App />)
    await pick('MONA-0001')
    await waitFor(() => expect(cards()).toHaveLength(25))

    const tabHold = gate()
    api.held.set('matches', tabHold)
    fireEvent.click(screen.getByRole('tab', { name: /Loans/ }))
    expect(await screen.findByText('Loading matches…')).toBeInTheDocument()
    tabHold.open()
    await waitFor(() => expect(cards()).toHaveLength(3))

    api.held.delete('matches')
    fireEvent.click(screen.getByRole('tab', { name: /Grants/ }))
    await waitFor(() => expect(cards()).toHaveLength(25))

    const pageHold = gate()
    api.held.set('matches', pageHold)
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }))
    const button = await screen.findByRole('button', { name: 'Loading more…' })
    expect(button).toBeDisabled()
    expect(cards()).toHaveLength(25) // cards already shown stay in place
    pageHold.open()
    await waitFor(() => expect(cards()).toHaveLength(50))
  })
})
