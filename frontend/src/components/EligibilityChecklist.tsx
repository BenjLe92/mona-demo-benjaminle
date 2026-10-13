import { OUTCOME_LABELS } from '../format'
import type { Eligibility } from '../types/api'

export function EligibilityChecklist({ eligibility }: { eligibility: Eligibility }) {
  return (
    <section className="panel">
      <h4>Eligibility checks</h4>
      <ul className="checks">
        {eligibility.checks.map((check, index) => (
          <li key={`${check.rule}-${index}`} className={`check check-${check.outcome}`}>
            <span className="check-outcome">{OUTCOME_LABELS[check.outcome]}</span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.reason}</p>
            </div>
          </li>
        ))}
      </ul>
      {eligibility.warnings.length > 0 && (
        <ul className="warnings" aria-label="Verification warnings">
          {eligibility.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
