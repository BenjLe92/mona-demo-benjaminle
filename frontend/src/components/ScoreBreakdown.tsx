import type { Relevance } from '../types/api'

export function ScoreBreakdown({ relevance }: { relevance: Relevance }) {
  return (
    <section className="panel">
      <h4>Relevance: {relevance.score} out of 100</h4>
      <ul className="components">
        {relevance.components.map((component) => (
          <li key={component.name}>
            <div className="component-head">
              <strong>{component.label}</strong>
              <span>
                {component.points} / {component.max}
              </span>
            </div>
            <div className="bar" aria-hidden="true">
              <div className="bar-fill" style={{ width: `${(component.points / component.max) * 100}%` }} />
            </div>
            <p>{component.reason}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
