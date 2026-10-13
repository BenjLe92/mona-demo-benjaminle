import { useEffect, useState } from 'react'
import { fetchMatches } from '../api/client'
import { STATUS_LABELS } from '../format'
import type { EligibilityStatus, MatchBucket, MatchResponse, StatusCounts } from '../types/api'
import { MatchCard } from './MatchCard'

const PAGE_SIZE = 25
const TABS: { bucket: MatchBucket; label: string }[] = [
  { bucket: 'grant', label: 'Grants' },
  { bucket: 'loan', label: 'Loans' },
  { bucket: 'coming_soon', label: 'Coming soon' },
]
const STATUSES: EligibilityStatus[] = ['likely_eligible', 'needs_verification', 'ineligible']

function actionable(counts: StatusCounts | undefined): number | null {
  return counts ? counts.likely_eligible + counts.needs_verification : null
}

export function MatchResults({ profileId }: { profileId: string }) {
  const [bucket, setBucket] = useState<MatchBucket>('grant')
  const [status, setStatus] = useState<EligibilityStatus | null>(null)
  const [includeIneligible, setIncludeIneligible] = useState(false)
  // `offset` is where the next page starts; `attempt` lets a failed page be requested again.
  const [page, setPage] = useState({ offset: 0, attempt: 0 })
  const [data, setData] = useState<MatchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    const query = { kind: bucket, status, includeIneligible, limit: PAGE_SIZE, offset: page.offset }
    fetchMatches(profileId, query, controller.signal)
      .then((response) => {
        // Later pages are appended to the cards already shown.
        setData((shown) =>
          page.offset === 0 || !shown ? response : { ...response, results: [...shown.results, ...response.results] },
        )
        setError(null)
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        // A failed first page leaves nothing valid to show; a failed later page keeps the cards.
        if (page.offset === 0) setData(null)
        setError(reason instanceof Error ? reason.message : 'Could not load matches.')
        setLoading(false)
      })
    return () => controller.abort()
  }, [profileId, bucket, status, includeIneligible, page])

  function changeView(update: () => void) {
    update()
    setPage({ offset: 0, attempt: 0 })
    setLoading(true)
  }

  function showMore() {
    setPage((current) => ({ offset: data?.results.length ?? 0, attempt: current.attempt + 1 }))
    setLoading(true)
  }

  const counts = data?.counts[bucket]
  // Loading a new view replaces the cards; loading a further page only adds to them.
  const loadingView = loading && page.offset === 0

  return (
    <section className="results">
      <div className="tabs" role="tablist">
        {TABS.map((tab) => {
          const count = actionable(data?.counts[tab.bucket])
          return (
            <button
              key={tab.bucket}
              type="button"
              role="tab"
              aria-selected={bucket === tab.bucket}
              className={bucket === tab.bucket ? 'tab active' : 'tab'}
              onClick={() => bucket !== tab.bucket && changeView(() => setBucket(tab.bucket))}
            >
              {tab.label}
              {count != null && <span className="tab-count">{count}</span>}
            </button>
          )
        })}
      </div>

      {bucket === 'coming_soon' && (
        <p className="notice">These opportunities are not accepting applications yet, so you cannot act on them today.</p>
      )}

      <div className="filters">
        <label>
          Status{' '}
          <select
            value={status ?? ''}
            onChange={(event) => changeView(() => setStatus((event.target.value || null) as EligibilityStatus | null))}
          >
            <option value="">All</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
                {counts ? ` (${counts[value]})` : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={includeIneligible}
            disabled={status !== null}
            onChange={(event) => changeView(() => setIncludeIneligible(event.target.checked))}
          />{' '}
          Show ineligible{counts ? ` (${counts.ineligible})` : ''}
        </label>
        {data && <span className="muted">Deadlines checked as of {data.as_of}</span>}
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loadingView && (
        <p className={data ? 'loading-note' : 'empty'} role="status">
          Loading matches…
        </p>
      )}
      {data && data.results.length === 0 && !loading && <p className="empty">No opportunities match these filters.</p>}
      {data && (
        <div className={loadingView ? 'cards loading' : 'cards'}>
          {data.results.map((match) => (
            <MatchCard key={match.opportunity_id} match={match} />
          ))}
        </div>
      )}
      {data && !loadingView && data.results.length < data.total && (
        <button type="button" className="more" onClick={showMore} disabled={loading}>
          {loading ? 'Loading more…' : `Show more (${data.results.length} of ${data.total})`}
        </button>
      )}
    </section>
  )
}
