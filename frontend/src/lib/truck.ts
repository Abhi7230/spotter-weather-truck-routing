import type { Checkpoint } from './types'

export interface TruckPosition {
  lat: number
  lon: number
  mile: number
  status: 'waiting' | 'driving' | 'arrived'
}

/**
 * Where the truck is at `time`, interpolated between the two checkpoints whose
 * ETAs bracket it. Used to show the truck on the map as the slider moves.
 */
export function truckPositionAt(checkpoints: Checkpoint[], time: Date): TruckPosition | null {
  if (!checkpoints.length) return null
  const t = time.getTime()
  const first = checkpoints[0]
  const last = checkpoints[checkpoints.length - 1]
  if (t < Date.parse(first.eta)) return { ...pick(first), status: 'waiting' }
  if (t >= Date.parse(last.eta)) return { ...pick(last), status: 'arrived' }

  for (let i = 1; i < checkpoints.length; i++) {
    const a = checkpoints[i - 1]
    const b = checkpoints[i]
    const ta = Date.parse(a.eta)
    const tb = Date.parse(b.eta)
    if (t <= tb) {
      const f = tb === ta ? 0 : (t - ta) / (tb - ta)
      return {
        lat: a.lat + (b.lat - a.lat) * f,
        lon: a.lon + (b.lon - a.lon) * f,
        mile: a.mile + (b.mile - a.mile) * f,
        status: 'driving',
      }
    }
  }
  return null
}

const pick = (c: Checkpoint) => ({ lat: c.lat, lon: c.lon, mile: c.mile })
