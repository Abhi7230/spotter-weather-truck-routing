import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import { nextHour, toLocalInputValue } from '../lib/format'
import type { Place, PlanRequest, TripPreset } from '../lib/types'
import { PlaceInput } from './PlaceInput'

const INTERVALS = [10, 25, 50]
const MAX_DAYS_AHEAD = 7

interface Props {
  loading: boolean
  /** Starting values, e.g. from a shared plan. Remount (via `key`) to apply new ones. */
  initial?: Partial<PlanRequest>
  onSubmit: (request: PlanRequest) => void
}

export function TripForm({ loading, initial, onSubmit }: Props) {
  const [presets, setPresets] = useState<TripPreset[]>([])
  const [origin, setOrigin] = useState<Place | null>(initial?.origin ?? null)
  const [destination, setDestination] = useState<Place | null>(initial?.destination ?? null)
  const [departure, setDeparture] = useState(() =>
    toLocalInputValue(initial?.departure ? new Date(initial.departure) : nextHour()),
  )
  const [now] = useState(() => new Date())
  const [loadLb, setLoadLb] = useState(initial?.load_lb ?? 35000)
  const [intervalMiles, setIntervalMiles] = useState(initial?.interval_miles ?? 25)
  const [simulateStorm, setSimulateStorm] = useState(initial?.simulate_storm ?? false)

  useEffect(() => {
    api.presets().then(setPresets).catch(() => setPresets([]))
  }, [])

  const applyPreset = (preset: TripPreset) => {
    setOrigin(preset.origin)
    setDestination(preset.destination)
    setLoadLb(preset.load_lb)
    setIntervalMiles(preset.interval_miles)
    setSimulateStorm(preset.simulate_storm)
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!origin || !destination) return
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lb: loadLb,
      interval_miles: intervalMiles,
      simulate_storm: simulateStorm,
    })
  }

  const maxDeparture = new Date(now.getTime() + MAX_DAYS_AHEAD * 86_400_000)

  return (
    <form className="trip-form" onSubmit={submit}>
      {presets.length > 0 && (
        <div className="field">
          <label htmlFor="preset">Try a sample trip</label>
          <select
            id="preset"
            defaultValue=""
            onChange={(e) => {
              const preset = presets.find((p) => p.id === Number(e.target.value))
              if (preset) applyPreset(preset)
            }}
          >
            <option value="" disabled>
              Choose a preset…
            </option>
            {presets.map((p) => (
              <option key={p.id} value={p.id} title={p.description}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <PlaceInput label="Origin" value={origin} onChange={setOrigin} />
      <PlaceInput label="Destination" value={destination} onChange={setDestination} />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            required
            value={departure}
            min={toLocalInputValue(now)}
            max={toLocalInputValue(maxDeparture)}
            onChange={(e) => setDeparture(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            required
            min={0}
            max={120000}
            step={500}
            value={loadLb}
            onChange={(e) => setLoadLb(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="field">
        <span className="label">Weather checkpoint every</span>
        <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
          {INTERVALS.map((miles) => (
            <button
              key={miles}
              type="button"
              role="radio"
              aria-checked={intervalMiles === miles}
              className={intervalMiles === miles ? 'active' : ''}
              onClick={() => setIntervalMiles(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
      </div>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={simulateStorm}
          onChange={(e) => setSimulateStorm(e.target.checked)}
        />
        <span>
          Simulate a storm on the fastest route
          <small>Demo mode: replaces the live forecast with a synthetic storm.</small>
        </span>
      </label>

      <button className="primary" type="submit" disabled={loading || !origin || !destination}>
        {loading ? 'Checking routes and weather…' : 'Plan routes'}
      </button>
    </form>
  )
}
