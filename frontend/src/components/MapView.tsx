import L, { type LatLngBoundsExpression } from 'leaflet'
import { Fragment, memo, useEffect, useMemo } from 'react'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet'
import { formatDateTime, formatDuration, formatMiles } from '../lib/format'
import { RISK_COLORS } from '../lib/risk'
import type { HeatMetric, PlanResult, RouteOption, TripPlan } from '../lib/types'
import type { TruckPosition } from '../lib/truck'
import { CorridorHeatLayer } from './CorridorHeatLayer'

interface Props {
  plan: TripPlan | null
  selectedId: number
  onSelect: (id: number) => void
  focus: { routeId: number; index: number } | null
  heat: { metric: HeatMetric; hour: number } | null
  truck: TruckPosition | null
}

const US_CENTER: [number, number] = [39.5, -98.35]
const truckIcon = L.divIcon({ className: 'truck-icon', html: '🚚', iconSize: [28, 28] })

export function MapView({ plan, selectedId, onSelect, focus, heat, truck }: Props) {
  const result = plan?.result
  return (
    <MapContainer center={US_CENTER} zoom={4} preferCanvas className="map" zoomControl>
      <TileLayer
        attribution='Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, &copy; OpenStreetMap contributors'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        maxZoom={18}
      />
      {result && heat && (
        <CorridorHeatLayer
          points={result.heatmap.points}
          stepDeg={result.heatmap.step_deg}
          levels={result.heatmap.frames[heat.hour]?.[heat.metric] ?? ''}
        />
      )}
      {result && plan && (
        <>
          <FitToPlan key={plan.id} result={result} />
          <Routes result={result} selectedId={selectedId} onSelect={onSelect} />
          <Endpoints plan={plan} />
          {focus && <FocusCheckpoint route={result.routes[focus.routeId]} index={focus.index} />}
        </>
      )}
      {truck && (
        <Marker position={[truck.lat, truck.lon]} icon={truckIcon} zIndexOffset={1000}>
          <Tooltip direction="top" offset={[0, -10]}>
            {truck.status === 'arrived'
              ? 'Arrived'
              : truck.status === 'waiting'
                ? 'Not departed yet'
                : `Mile ${Math.round(truck.mile)}`}
          </Tooltip>
        </Marker>
      )}
    </MapContainer>
  )
}

function FitToPlan({ result }: { result: PlanResult }) {
  const map = useMap()
  useEffect(() => {
    const bounds = result.routes.flatMap((r) => r.geometry) as LatLngBoundsExpression
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, result])
  return null
}

function FocusCheckpoint({ route, index }: { route: RouteOption; index: number }) {
  const map = useMap()
  useEffect(() => {
    const cp = route.checkpoints[index]
    if (cp) map.flyTo([cp.lat, cp.lon], Math.max(map.getZoom(), 8), { duration: 0.6 })
  }, [map, route, index])
  return null
}

const Endpoints = memo(function Endpoints({ plan }: { plan: TripPlan }) {
  return (
    <>
      {[plan.origin, plan.destination].map((place, i) => (
        <CircleMarker
          key={i}
          center={[place.lat, place.lon]}
          radius={9}
          pathOptions={{ color: '#fff', weight: 3, fillColor: '#0b3d4c', fillOpacity: 1 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            {i === 0 ? 'Origin' : 'Destination'}: {place.label}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
})

// Memoised so moving the forecast slider doesn't re-render ~150 checkpoint markers.
const Routes = memo(function Routes({
  result,
  selectedId,
  onSelect,
}: {
  result: PlanResult
  selectedId: number
  onSelect: (id: number) => void
}) {
  // Draw the selected route last so it sits on top.
  const ordered = useMemo(
    () => [...result.routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId)),
    [result, selectedId],
  )
  return (
    <>
      {ordered.map((route) => {
        const selected = route.id === selectedId
        const recommended = route.id === result.recommended_route_id
        const mid = route.geometry[Math.floor(route.geometry.length / 2)]
        return (
          <Fragment key={route.id}>
            <Polyline
              positions={route.geometry}
              pathOptions={{
                color: selected ? '#0b3d4c' : '#6b7c85',
                weight: selected ? 6 : 4,
                opacity: selected ? 0.95 : 0.55,
              }}
              eventHandlers={{ click: () => onSelect(route.id) }}
            />
            <CircleMarker
              center={mid}
              radius={1}
              pathOptions={{ opacity: 0, fillOpacity: 0 }}
              eventHandlers={{ click: () => onSelect(route.id) }}
            >
              <Tooltip permanent direction="center" className={`route-label ${selected ? 'selected' : ''}`}>
                {route.name}
                {recommended ? ' ★' : ''} · {formatDuration(route.duration_seconds)} ·{' '}
                {formatMiles(route.distance_miles)} · {route.worst_risk}
              </Tooltip>
            </CircleMarker>
            {route.checkpoints.map((cp) => (
              <CircleMarker
                key={cp.mile}
                center={[cp.lat, cp.lon]}
                radius={selected ? 6 : 3.5}
                pathOptions={{
                  color: '#fff',
                  weight: selected ? 1.5 : 1,
                  fillColor: RISK_COLORS[cp.risk],
                  fillOpacity: selected ? 1 : 0.7,
                }}
              >
                <Popup>
                  <div className="cp-popup">
                    <strong>
                      {route.name} · mile {Math.round(cp.mile)}
                    </strong>
                    <div>ETA {formatDateTime(cp.eta)}</div>
                    <div>
                      Risk: <b style={{ color: RISK_COLORS[cp.risk] }}>{cp.risk}</b>
                    </div>
                    {cp.weather && (
                      <div>
                        Wind {cp.weather.wind_mph.toFixed(1)} mph (gusts{' '}
                        {Math.round(cp.weather.gust_mph)}) · Rain {cp.weather.rain_in_hr.toFixed(2)}{' '}
                        in/hr · Snow {cp.weather.snow_in_hr.toFixed(2)} in/hr ·{' '}
                        {Math.round(cp.weather.temperature_f)}°F
                      </div>
                    )}
                    {cp.reasons.length > 0 && (
                      <ul>
                        {cp.reasons.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </Fragment>
        )
      })}
    </>
  )
})
