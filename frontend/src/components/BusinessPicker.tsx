import { useState } from 'react'
import type { BusinessSummary } from '../types/api'

interface Props {
  businesses: BusinessSummary[]
  selectedId: string | null
  onSelect: (profileId: string) => void
}

export function BusinessPicker({ businesses, selectedId, onSelect }: Props) {
  const [search, setSearch] = useState('')
  const needle = search.trim().toLowerCase()
  const visible = businesses.filter((b) =>
    `${b.profile_id} ${b.city} ${b.state} ${b.industry_label ?? ''}`.toLowerCase().includes(needle),
  )

  return (
    <nav className="picker" aria-label="Business profiles">
      <input
        type="search"
        placeholder="Search by ID, city, state or industry"
        aria-label="Search businesses"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      <p className="picker-count">
        {visible.length} of {businesses.length} businesses
      </p>
      <ul>
        {visible.map((b) => (
          <li key={b.profile_id}>
            <button
              type="button"
              className={b.profile_id === selectedId ? 'picker-item selected' : 'picker-item'}
              aria-current={b.profile_id === selectedId}
              onClick={() => onSelect(b.profile_id)}
            >
              <strong>{b.profile_id}</strong>
              <span>
                {b.city}, {b.state}
              </span>
              <span className="muted">{b.industry_label ?? 'Industry not on file'}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
