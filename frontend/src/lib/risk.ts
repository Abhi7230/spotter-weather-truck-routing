import type { RiskLabel } from './types'

export const RISK_LEVELS: RiskLabel[] = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const RISK_COLORS: Record<RiskLabel, string> = {
  Low: '#2e9d5b',
  Moderate: '#e3b505',
  High: '#f07c1b',
  Severe: '#d62c2c',
  'No Travel': '#7a1fa2',
}

export const riskColor = (score: number) => RISK_COLORS[RISK_LEVELS[score] ?? 'Low']
