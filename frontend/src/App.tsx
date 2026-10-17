import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckpointTable } from './components/CheckpointTable'
import { ForecastPanel } from './components/ForecastPanel'
import { MapView } from './components/MapView'
import { RouteCards } from './components/RouteCards'
import { TripForm } from './components/TripForm'
import { api } from './lib/api'
import { truckPositionAt } from './lib/truck'
import type { HeatMetric, PlanRequest, TripPlan } from './lib/types'

function planIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('plan')
}

export default function App() {
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [loading, setLoading] = useState(() => planIdFromUrl() !== null)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState(0)
  const [focus, setFocus] = useState<{ routeId: number; index: number } | null>(null)
  const [hour, setHour] = useState(0)
  const [metric, setMetric] = useState<HeatMetric>('risk')
  const [heatVisible, setHeatVisible] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [copied, setCopied] = useState(false)

  const showPlan = useCallback((next: TripPlan) => {
    setPlan(next)
    setSelectedId(next.result.recommended_route_id)
    setFocus(null)
    setHour(0)
    setPlaying(false)
  }, [])

  // Open a shared plan from ?plan=<id>.
  useEffect(() => {
    const id = planIdFromUrl()
    if (!id) return
    api
      .getPlan(id)
      .then(showPlan)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [showPlan])

  const submit = async (request: PlanRequest) => {
    setLoading(true)
    setError(null)
    try {
      const created = await api.createPlan(request)
      showPlan(created)
      window.history.replaceState(null, '', `?plan=${created.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const focusCheckpoint = useCallback(
    (routeId: number, index: number) => setFocus({ routeId, index }),
    [],
  )

  const selectedRoute = plan?.result.routes.find((r) => r.id === selectedId) ?? null
  const truck = useMemo(() => {
    if (!plan || !selectedRoute) return null
    const time = new Date(Date.parse(plan.result.heatmap.start) + hour * 3_600_000)
    return truckPositionAt(selectedRoute.checkpoints, time)
  }, [plan, selectedRoute, hour])


  const copyLink = async () => {
    await navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <header>
          <h1>Weather-Aware Truck Routing</h1>
          <p>Compare three routes by weather risk at your truck's ETA, load weight and drive time.</p>
        </header>

        <TripForm key={plan?.id} loading={loading} initial={plan ?? undefined} onSubmit={submit} />
        {error && <div className="error" role="alert">{error}</div>}

        {plan && (
          <>
            <div className="plan-meta">
              <span>
                {plan.simulate_storm ? 'Simulated storm' : 'Live forecast (Open-Meteo)'} ·{' '}
                {plan.load_lb.toLocaleString()} lb · every {plan.interval_miles} mi
              </span>
              <button type="button" className="link" onClick={copyLink}>
                {copied ? 'Copied!' : 'Copy share link'}
              </button>
            </div>
            <RouteCards result={plan.result} selectedId={selectedId} onSelect={setSelectedId} />
            {selectedRoute && (
              <CheckpointTable route={selectedRoute} onFocus={focusCheckpoint} />
            )}
          </>
        )}
      </aside>

      <main className="map-area">
        <MapView
          plan={plan}
          selectedId={selectedId}
          onSelect={setSelectedId}
          focus={focus}
          heat={plan && heatVisible ? { metric, hour } : null}
          truck={plan ? truck : null}
        />
        {plan && (
          <ForecastPanel
            start={plan.result.heatmap.start}
            hour={hour}
            onHourChange={setHour}
            metric={metric}
            onMetricChange={setMetric}
            visible={heatVisible}
            onVisibleChange={setHeatVisible}
            playing={playing}
            onPlayingChange={setPlaying}
            truckLabel={
              truck
                ? truck.status === 'driving'
                  ? `${selectedRoute?.name} at mile ${Math.round(truck.mile)}`
                  : truck.status === 'arrived'
                    ? `${selectedRoute?.name} arrived`
                    : 'not departed'
                : null
            }
          />
        )}
        {loading && <div className="map-loading">Fetching routes and forecasts…</div>}
      </main>
    </div>
  )
}
