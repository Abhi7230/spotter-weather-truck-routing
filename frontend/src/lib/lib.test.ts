import { errorMessage } from './api'
import { formatDuration, nextHour, toLocalInputValue } from './format'
import { truckPositionAt } from './truck'
import type { Checkpoint } from './types'

const cp = (mile: number, eta: string, lat: number, lon: number): Checkpoint => ({
  mile,
  eta,
  lat,
  lon,
  weather: null,
  risk: 'Low',
  risk_score: 0,
  reasons: [],
})

describe('truckPositionAt', () => {
  const checkpoints = [
    cp(0, '2026-10-18T12:00:00Z', 40, -100),
    cp(50, '2026-10-18T13:00:00Z', 40, -99),
    cp(100, '2026-10-18T14:00:00Z', 40, -98),
  ]

  it('interpolates between bracketing checkpoints', () => {
    const pos = truckPositionAt(checkpoints, new Date('2026-10-18T13:30:00Z'))
    expect(pos).toMatchObject({ status: 'driving', mile: 75, lon: -98.5 })
  })

  it('reports waiting before departure and arrived after the last ETA', () => {
    expect(truckPositionAt(checkpoints, new Date('2026-10-18T11:00:00Z'))?.status).toBe('waiting')
    expect(truckPositionAt(checkpoints, new Date('2026-10-19T00:00:00Z'))).toMatchObject({
      status: 'arrived',
      mile: 100,
    })
  })

  it('handles an empty route', () => {
    expect(truckPositionAt([], new Date())).toBeNull()
  })
})

describe('formatting', () => {
  it('formats durations', () => {
    expect(formatDuration(17.8 * 3600)).toBe('17h 48m')
    expect(formatDuration(25 * 60)).toBe('25m')
  })

  it('rounds the default departure up to the next hour', () => {
    const d = nextHour(new Date(2026, 9, 17, 15, 48))
    expect(toLocalInputValue(d)).toBe('2026-10-17T16:00')
  })
})

describe('errorMessage', () => {
  it('reads DRF detail and field errors', () => {
    expect(errorMessage({ detail: 'Routing failed' })).toBe('Routing failed')
    expect(errorMessage({ load_lb: ['Ensure this value is >= 0.'] })).toBe(
      'load lb: Ensure this value is >= 0.',
    )
    expect(errorMessage({ non_field_errors: ['Same place.'] })).toBe('Same place.')
    expect(errorMessage(null)).toBeNull()
  })
})
