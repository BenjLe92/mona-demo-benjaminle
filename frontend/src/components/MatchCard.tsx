import { useState } from 'react'
import { categoryLabel, formatAmount } from '../format'
import type { Match } from '../types/api'
import { EligibilityChecklist } from './EligibilityChecklist'
import { ScoreBreakdown } from './ScoreBreakdown'
import { StatusBadge } from './StatusBadge'

export function MatchCard({ match }: { match: Match }) {
  const [open, setOpen] = useState(false)
  const actionLabel = match.kind === 'loan' ? 'Go to lender' : 'View opportunity'

  return (
    <article className="card">
      <header className="card-head">
        <div>
          <h3>{match.name}</h3>
          <p className="meta">
            {categoryLabel(match.category)} · {formatAmount(match.amount)}
            {match.deadline && ` · ${match.deadline.label}`}
          </p>
        </div>
        <div className="card-status">
          <StatusBadge status={match.eligibility.status} />
          <span className="score" title="Relevance score">
            {match.relevance.score}
            <small> / 100</small>
          </span>
        </div>
      </header>

      <dl className="why">
        <dt>Eligibility</dt>
        <dd>{match.eligibility.summary}</dd>
        <dt>Relevance</dt>
        <dd>{match.relevance.summary}</dd>
      </dl>

      <div className="card-actions">
        <button type="button" className="link-button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? 'Hide details' : 'Show details'}
        </button>
        <a href={match.url} target="_blank" rel="noreferrer">
          {actionLabel}
        </a>
      </div>

      {open && (
        <div className="card-details">
          <EligibilityChecklist eligibility={match.eligibility} />
          <ScoreBreakdown relevance={match.relevance} />
          {Object.keys(match.details).length > 0 && (
            <section className="panel">
              <h4>Details</h4>
              <dl className="facts">
                {Object.entries(match.details).map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          {match.description && (
            <section className="panel">
              <h4>About</h4>
              <p className="long-text">{match.description}</p>
            </section>
          )}
          {match.criteria_text && (
            <section className="panel">
              <h4>Full criteria from the listing</h4>
              <p className="long-text">{match.criteria_text}</p>
            </section>
          )}
        </div>
      )}
    </article>
  )
}
