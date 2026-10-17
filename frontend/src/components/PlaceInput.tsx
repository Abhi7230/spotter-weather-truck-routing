import { useEffect, useId, useState } from 'react'
import { api } from '../lib/api'
import type { Place } from '../lib/types'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
}

/** Text box with debounced place suggestions. A place must be picked from the list. */
export function PlaceInput({ label, value, onChange }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [suggestions, setSuggestions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)

  // Show the label when the parent picks a place (e.g. from a preset).
  const [shownValue, setShownValue] = useState(value)
  if (value !== shownValue) {
    setShownValue(value)
    if (value) setText(value.label)
  }

  useEffect(() => {
    if (!open || text.trim().length < 3 || text === value?.label) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api
        .geocode(text, controller.signal)
        .then(setSuggestions)
        .catch(() => setSuggestions([]))
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [text, open, value])

  const choose = (place: Place) => {
    onChange(place)
    setText(place.label)
    setSuggestions([])
    setOpen(false)
  }

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={text}
        placeholder="City or address"
        autoComplete="off"
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
          if (value) onChange(null)
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => setOpen(true)}
      />
      {open && suggestions.length > 0 && (
        <ul className="suggestions" role="listbox">
          {suggestions.map((place) => (
            <li key={`${place.lat},${place.lon}`}>
              <button type="button" onMouseDown={() => choose(place)}>
                {place.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
