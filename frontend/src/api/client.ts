import type {
  BusinessProfile,
  BusinessSummary,
  EligibilityStatus,
  MatchBucket,
  MatchResponse,
} from '../types/api'

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    const body: { detail?: unknown } = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export function fetchBusinesses(signal?: AbortSignal): Promise<BusinessSummary[]> {
  return get('/api/businesses', signal)
}

export function fetchBusiness(profileId: string, signal?: AbortSignal): Promise<BusinessProfile> {
  return get(`/api/businesses/${encodeURIComponent(profileId)}`, signal)
}

export interface MatchQuery {
  kind: MatchBucket
  status: EligibilityStatus | null
  includeIneligible: boolean
  limit: number
}

export function fetchMatches(profileId: string, query: MatchQuery, signal?: AbortSignal): Promise<MatchResponse> {
  const params = new URLSearchParams({
    kind: query.kind,
    include_ineligible: String(query.includeIneligible),
    limit: String(query.limit),
  })
  if (query.status) params.set('status', query.status)
  return get(`/api/businesses/${encodeURIComponent(profileId)}/matches?${params}`, signal)
}
