import { useEffect, useState } from 'react'
import { fetchMatches } from '../api/client'
import { STATUS_LABELS } from '../format'
import type { EligibilityStatus, MatchBucket, MatchResponse, StatusCounts } from '../types/api'
import { MatchCard } from './MatchCard'

const PAGE_SIZE = 25
const MAX_LIMIT = 100 // the API's upper bound for `limit`
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
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [data, setData] = useState<MatchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    fetchMatches(profileId, { kind: bucket, status, includeIneligible, limit }, controller.signal)
      .then((response) => {
        setData(response)
        setError(null)
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Could not load matches.')
        setLoading(false)
      })
    return () => controller.abort()
  }, [profileId, bucket, status, includeIneligible, limit])

  function changeView(update: () => void) {
    update()
    setLimit(PAGE_SIZE)
    setLoading(true)
  }

  function showMore() {
    setLimit(Math.min(limit + PAGE_SIZE, MAX_LIMIT))
    setLoading(true)
  }

  const counts = data?.counts[bucket]

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
      {!error && data && data.results.length === 0 && !loading && (
        <p className="empty">No opportunities match these filters.</p>
      )}
      {!error && data && (
        <div className={loading ? 'cards loading' : 'cards'}>
          {data.results.map((match) => (
            <MatchCard key={match.opportunity_id} match={match} />
          ))}
        </div>
      )}
      {!error && !data && loading && <p className="empty">Loading matches…</p>}
      {!error && data && data.results.length < data.total && limit < MAX_LIMIT && (
        <button type="button" className="more" onClick={showMore}>
          Show more ({data.results.length} of {data.total})
        </button>
      )}
    </section>
  )
}
