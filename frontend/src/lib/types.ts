// Shapes returned by the Django API (see backend/trips/planner.py).

export type RiskLabel = 'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel'

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface CheckpointWeather {
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
  temperature_f: number
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  weather: CheckpointWeather | null
  risk: RiskLabel
  risk_score: number
  reasons: string[]
}

export interface RouteOption {
  id: number
  name: string
  summary: string
  distance_miles: number
  duration_seconds: number
  arrival: string
  miles_by_risk: Record<RiskLabel, number>
  average_risk: number
  worst_risk: RiskLabel
  rank: number
  geometry: [number, number][]
  checkpoints: Checkpoint[]
}

export type HeatMetric = 'risk' | 'wind' | 'rain' | 'snow'

export interface Heatmap {
  start: string
  step_deg: number
  points: [number, number][]
  /** One entry per slider hour; each metric is a string of risk digits, one per point. */
  frames: Record<HeatMetric, string>[]
}

export interface PlanResult {
  recommended_route_id: number
  recommendation_reason: string
  routes: RouteOption[]
  heatmap: Heatmap
  risk_levels: RiskLabel[]
}

export interface TripPlan {
  id: string
  created_at: string
  origin: Place
  destination: Place
  departure: string
  load_lb: number
  interval_miles: number
  simulate_storm: boolean
  result: PlanResult
}

export interface TripPreset {
  id: number
  name: string
  description: string
  origin: Place
  destination: Place
  load_lb: number
  interval_miles: number
  simulate_storm: boolean
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string
  load_lb: number
  interval_miles: number
  simulate_storm: boolean
}
