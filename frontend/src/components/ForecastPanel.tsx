import { useEffect } from 'react'
import { formatDateTime } from '../lib/format'
import { RISK_COLORS, RISK_LEVELS } from '../lib/risk'
import type { HeatMetric } from '../lib/types'

export const MAX_HOUR = 48

const METRICS: { value: HeatMetric; label: string }[] = [
  { value: 'risk', label: 'Overall risk' },
  { value: 'wind', label: 'Wind (load-adjusted)' },
  { value: 'rain', label: 'Rain' },
  { value: 'snow', label: 'Snow' },
]

interface Props {
  start: string
  hour: number
  onHourChange: (hour: number) => void
  metric: HeatMetric
  onMetricChange: (metric: HeatMetric) => void
  visible: boolean
  onVisibleChange: (visible: boolean) => void
  playing: boolean
  onPlayingChange: (playing: boolean) => void
  truckLabel: string | null
}

/** Heatmap controls floating over the map: 0-48 h slider, play, metric and legend. */
export function ForecastPanel(props: Props) {
  const { hour, onHourChange, playing, onPlayingChange } = props

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      onHourChange(hour >= MAX_HOUR ? 0 : hour + 1)
    }, 350)
    return () => window.clearInterval(timer)
  }, [playing, hour, onHourChange])

  const time = new Date(Date.parse(props.start) + hour * 3_600_000).toISOString()

  return (
    <div className="forecast-panel">
      <div className="forecast-top">
        <label className="checkbox inline">
          <input
            type="checkbox"
            checked={props.visible}
            onChange={(e) => props.onVisibleChange(e.target.checked)}
          />
          Weather heatmap
        </label>
        <select
          aria-label="Heatmap layer"
          value={props.metric}
          onChange={(e) => props.onMetricChange(e.target.value as HeatMetric)}
        >
          {METRICS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>
      <div className="slider-row">
        <button
          type="button"
          className="play"
          onClick={() => onPlayingChange(!playing)}
          aria-label={playing ? 'Pause' : 'Play forecast'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          min={0}
          max={MAX_HOUR}
          step={1}
          value={hour}
          aria-label="Forecast hour"
          onChange={(e) => onHourChange(Number(e.target.value))}
        />
      </div>
      <div className="slider-caption">
        <strong>+{hour}h</strong> · {formatDateTime(time)}
        {props.truckLabel && <span className="truck-label"> · 🚚 {props.truckLabel}</span>}
      </div>
      <div className="legend">
        {RISK_LEVELS.map((level) => (
          <span key={level}>
            <i style={{ background: RISK_COLORS[level] }} />
            {level}
          </span>
        ))}
      </div>
    </div>
  )
}
