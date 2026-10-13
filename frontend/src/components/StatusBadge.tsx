import { STATUS_LABELS } from '../format'
import type { EligibilityStatus } from '../types/api'

export function StatusBadge({ status }: { status: EligibilityStatus }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status]}</span>
}
