import { useEffect, useState } from 'react'
import { fetchBusiness, fetchBusinesses } from './api/client'
import { BusinessPicker } from './components/BusinessPicker'
import { MatchResults } from './components/MatchResults'
import { ProfileSummary } from './components/ProfileSummary'
import type { BusinessProfile, BusinessSummary } from './types/api'

function App() {
  const [businesses, setBusinesses] = useState<BusinessSummary[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchBusinesses(controller.signal)
      .then((loaded) => {
        setBusinesses(loaded)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : 'Could not load businesses.')
        }
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    fetchBusiness(selectedId, controller.signal)
      .then((loaded) => {
        setProfile(loaded)
        setError(null) // a successful load clears any earlier failure message
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : 'Could not load the business profile.')
        }
      })
    return () => controller.abort()
  }, [selectedId, attempt])

  function selectBusiness(profileId: string) {
    setSelectedId(profileId)
    setAttempt((count) => count + 1) // refetch even when the same business is picked again after a failure
    setError(null) // the message belonged to the previous request
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Mona funding matcher</h1>
        {businesses ? (
          <BusinessPicker businesses={businesses} selectedId={selectedId} onSelect={selectBusiness} />
        ) : (
          !error && (
            <p className="empty" role="status">
              Loading businesses…
            </p>
          )
        )}
      </aside>
      <main className="main">
        {error && (
          <p className="error" role="alert">
            {error} Check that the API is running on port 8000.
          </p>
        )}
        {!selectedId && !error && (
          <p className="empty">Select a business to see the grants and loans it may qualify for.</p>
        )}
        {selectedId && profile?.profile_id !== selectedId && !error && (
          <p className="empty" role="status">
            Loading business profile…
          </p>
        )}
        {selectedId && profile?.profile_id === selectedId && (
          <>
            <ProfileSummary profile={profile} />
            {/* key resets tab, filters and paging when the business changes */}
            <MatchResults key={selectedId} profileId={selectedId} />
          </>
        )}
      </main>
    </div>
  )
}

export default App
