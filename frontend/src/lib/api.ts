import type { Place, PlanRequest, TripPlan, TripPreset } from './types'

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(errorMessage(body) ?? `Request failed (${response.status})`)
  return body as T
}

/** Flatten DRF error bodies ({detail} or {field: [msgs]}) into one readable line. */
export function errorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  if ('detail' in body && typeof body.detail === 'string') return body.detail
  const messages = Object.entries(body).flatMap(([field, value]) => {
    const list = Array.isArray(value) ? value : [value]
    return list.map((v) => {
      const text = typeof v === 'string' ? v : JSON.stringify(v)
      return field === 'non_field_errors' ? text : `${field.replace('_', ' ')}: ${text}`
    })
  })
  return messages.length ? messages.join(' ') : null
}

export const api = {
  geocode: (q: string, signal?: AbortSignal) =>
    request<Place[]>(`/geocode/?q=${encodeURIComponent(q)}`, { signal }),
  presets: () => request<TripPreset[]>('/presets/'),
  createPlan: (body: PlanRequest) =>
    request<TripPlan>('/plans/', { method: 'POST', body: JSON.stringify(body) }),
  getPlan: (id: string) => request<TripPlan>(`/plans/${id}/`),
}
