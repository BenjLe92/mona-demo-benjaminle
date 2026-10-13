import type { BusinessProfile, TriState } from '../types/api'

const NOT_ON_FILE = 'Not on file'
const FLAG_TEXT: Record<TriState, string> = { yes: 'Yes', no: 'No', unknown: NOT_ON_FILE }

export function ProfileSummary({ profile }: { profile: BusinessProfile }) {
  const facts: [string, string | null][] = [
    ['Industry', profile.industry_label],
    ['Business type', profile.business_type],
    ['Time in business', profile.years_in_business_label],
    ['Annual revenue', profile.revenue_label],
    ['Credit score', profile.credit_score_label],
    ['Employees', profile.employees_label],
    ['Funding uses', profile.funding_uses.join(', ') || null],
    ['Funding timing', profile.funding_timing],
  ]
  const flags: [string, TriState][] = [
    ['Woman-owned', profile.woman_owned],
    ['Black-owned', profile.black_owned],
    ['BIPOC-owned', profile.bipoc_owned],
    ['Veteran-owned', profile.veteran_owned],
    ['Nonprofit', profile.nonprofit],
    ['Brick-and-mortar', profile.brick_and_mortar],
  ]

  return (
    <section className="profile">
      <h2>
        {profile.profile_id} <span className="muted">· {profile.city}, {profile.state_name}</span>
      </h2>
      <dl className="facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className={value ? undefined : 'unknown'}>{value ?? NOT_ON_FILE}</dd>
          </div>
        ))}
        {flags.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className={value === 'unknown' ? 'unknown' : undefined}>{FLAG_TEXT[value]}</dd>
          </div>
        ))}
      </dl>
      {profile.unknown_fields.length > 0 && (
        <p className="notice">
          {profile.unknown_fields.length} detail{profile.unknown_fields.length === 1 ? ' is' : 's are'} not on file.
          Opportunities that depend on them are marked Needs Verification, not ruled in or out.
        </p>
      )}
    </section>
  )
}
