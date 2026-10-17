import { fireEvent, render, screen } from '@testing-library/react'
import type { PlanResult, RouteOption } from '../lib/types'
import { RouteCards } from './RouteCards'

const route = (id: number, overrides: Partial<RouteOption> = {}): RouteOption => ({
  id,
  name: `Route ${'ABC'[id]}`,
  summary: 'I 80',
  distance_miles: 1000 + id * 100,
  duration_seconds: 64000 + id * 3600,
  arrival: '2026-10-19T06:00:00Z',
  miles_by_risk: { Low: 1000, Moderate: 0, High: 0, Severe: 0, 'No Travel': 0 },
  average_risk: 0,
  worst_risk: 'Low',
  rank: id + 1,
  geometry: [],
  checkpoints: [],
  ...overrides,
})

const result = (routes: RouteOption[], recommended = 1): PlanResult => ({
  recommended_route_id: recommended,
  recommendation_reason: 'Fewest Severe miles (0 mi vs 50 mi on Route A).',
  routes,
  heatmap: { start: '2026-10-18T12:00:00Z', step_deg: 0.5, points: [], frames: [] },
  risk_levels: ['Low', 'Moderate', 'High', 'Severe', 'No Travel'],
})

describe('RouteCards', () => {
  it('marks the recommended route and explains why', () => {
    render(<RouteCards result={result([route(0), route(1)])} selectedId={0} onSelect={() => {}} />)
    expect(screen.getByText('Recommended: Route B')).toBeInTheDocument()
    expect(screen.getByText(/Fewest Severe miles/)).toBeInTheDocument()
    const badge = screen.getByText('Recommended', { selector: '.badge' })
    expect(badge.closest('button')).toHaveTextContent('Route B')
  })

  it('selects a route on click', () => {
    const onSelect = vi.fn()
    render(<RouteCards result={result([route(0), route(1)])} selectedId={0} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /Route B/ }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('warns when every route crosses No Travel weather', () => {
    const blocked = { Low: 900, Moderate: 0, High: 0, Severe: 0, 'No Travel': 100 }
    const routes = [route(0, { miles_by_risk: blocked }), route(1, { miles_by_risk: blocked })]
    render(<RouteCards result={result(routes)} selectedId={0} onSelect={() => {}} />)
    expect(screen.getByText(/Consider leaving later/)).toBeInTheDocument()
  })
})
