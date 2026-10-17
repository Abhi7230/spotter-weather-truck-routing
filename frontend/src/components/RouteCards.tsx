import { formatDateTime, formatDuration, formatMiles } from '../lib/format'
import type { PlanResult } from '../lib/types'
import { RiskBar, RiskChip } from './RiskBar'

interface Props {
  result: PlanResult
  selectedId: number
  onSelect: (id: number) => void
}

export function RouteCards({ result, selectedId, onSelect }: Props) {
  const allBlocked = result.routes.every((r) => r.miles_by_risk['No Travel'] > 0)
  return (
    <section className="route-cards">
      <div className="recommendation">
        <strong>
          Recommended: {result.routes.find((r) => r.id === result.recommended_route_id)?.name}
        </strong>
        <p>{result.recommendation_reason}</p>
        {allBlocked && (
          <p className="warning">
            Every route crosses No Travel weather at this departure time. Consider leaving later.
          </p>
        )}
      </div>

      {result.routes.map((route) => {
        const recommended = route.id === result.recommended_route_id
        const m = route.miles_by_risk
        return (
          <button
            key={route.id}
            type="button"
            className={`route-card ${route.id === selectedId ? 'selected' : ''}`}
            onClick={() => onSelect(route.id)}
            aria-pressed={route.id === selectedId}
          >
            <div className="route-card-header">
              <span className="route-name">
                {route.name}
                {recommended && <span className="badge">Recommended</span>}
              </span>
              <RiskChip level={route.worst_risk} />
            </div>
            <div className="route-summary">{route.summary || 'Unnamed roads'}</div>
            <div className="route-stats">
              <span>{formatMiles(route.distance_miles)}</span>
              <span>{formatDuration(route.duration_seconds)}</span>
              <span>Arrive {formatDateTime(route.arrival)}</span>
            </div>
            <RiskBar milesByRisk={m} />
            <div className="route-risk-stats">
              <span>Severe+ {Math.round(m.Severe + m['No Travel'])} mi</span>
              <span>High {Math.round(m.High)} mi</span>
              <span>Avg risk {route.average_risk.toFixed(2)}</span>
            </div>
          </button>
        )
      })}
    </section>
  )
}
