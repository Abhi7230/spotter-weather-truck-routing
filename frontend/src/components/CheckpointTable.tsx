import { formatDateTime } from '../lib/format'
import type { RouteOption } from '../lib/types'
import { RiskChip } from './RiskBar'

interface Props {
  route: RouteOption
  onFocus: (index: number) => void
}

export function CheckpointTable({ route, onFocus }: Props) {
  return (
    <section className="checkpoints">
      <h3>
        {route.name} checkpoints <small>({route.checkpoints.length})</small>
      </h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th title="Sustained wind (gusts)">Wind mph</th>
              <th title="Rain in/hr">Rain</th>
              <th title="Snow in/hr">Snow</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((cp, i) => (
              <tr key={cp.mile} onClick={() => onFocus(i)} title={cp.reasons.join('\n')}>
                <td>{Math.round(cp.mile)}</td>
                <td>{formatDateTime(cp.eta)}</td>
                <td>
                  <RiskChip level={cp.risk} />
                </td>
                <td>
                  {cp.weather
                    ? `${Math.round(cp.weather.wind_mph)} (${Math.round(cp.weather.gust_mph)})`
                    : '–'}
                </td>
                <td>{cp.weather?.rain_in_hr.toFixed(2) ?? '–'}</td>
                <td>{cp.weather?.snow_in_hr.toFixed(2) ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
