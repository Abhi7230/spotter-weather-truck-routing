import { RISK_COLORS, RISK_LEVELS } from '../lib/risk'
import type { RiskLabel } from '../lib/types'

/** Stacked bar of how many miles fall in each risk level. */
export function RiskBar({ milesByRisk }: { milesByRisk: Record<RiskLabel, number> }) {
  const total = RISK_LEVELS.reduce((sum, level) => sum + milesByRisk[level], 0) || 1
  return (
    <div className="risk-bar" aria-label="Miles by risk level">
      {RISK_LEVELS.filter((level) => milesByRisk[level] > 0).map((level) => (
        <span
          key={level}
          style={{ width: `${(milesByRisk[level] / total) * 100}%`, background: RISK_COLORS[level] }}
          title={`${level}: ${Math.round(milesByRisk[level])} mi`}
        />
      ))}
    </div>
  )
}

export function RiskChip({ level }: { level: RiskLabel }) {
  return (
    <span className="risk-chip" style={{ background: RISK_COLORS[level] }}>
      {level}
    </span>
  )
}
