import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { riskColor } from '../lib/risk'

interface Props {
  points: [number, number][]
  /** One risk digit (0-4) per point, as sent by the API. */
  levels: string
  stepDeg: number
}

// Low stays faint so the corridor is visible without hiding the base map.
const ALPHA_BY_LEVEL = [0.16, 0.38, 0.48, 0.58, 0.66]

/**
 * Draws the corridor grid as coloured cells on a single canvas, blurred with CSS
 * so it reads as a continuous heatmap. Redrawing ~400 rectangles takes well under
 * a millisecond, so dragging the forecast slider stays at 60 fps.
 */
export function CorridorHeatLayer({ points, levels, stepDeg }: Props) {
  const map = useMap()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const pane = map.getPane('heat') ?? map.createPane('heat')
    pane.style.zIndex = '350' // above tiles, below routes
    pane.style.pointerEvents = 'none'
    const canvas = L.DomUtil.create('canvas', 'heat-canvas', pane)
    canvasRef.current = canvas
    return () => {
      canvas.remove()
      canvasRef.current = null
    }
  }, [map])

  useEffect(() => {
    const draw = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const size = map.getSize()
      const ratio = window.devicePixelRatio || 1
      canvas.width = size.x * ratio
      canvas.height = size.y * ratio
      canvas.style.width = `${size.x}px`
      canvas.style.height = `${size.y}px`
      canvas.style.visibility = 'visible'
      L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]))

      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.scale(ratio, ratio)
      const half = stepDeg / 2
      let cellPx = 0
      points.forEach(([lat, lon], i) => {
        const level = levels.charCodeAt(i) - 48
        const nw = map.latLngToContainerPoint([lat + half, lon - half])
        const se = map.latLngToContainerPoint([lat - half, lon + half])
        cellPx = Math.max(cellPx, se.x - nw.x)
        ctx.globalAlpha = ALPHA_BY_LEVEL[level] ?? 0
        ctx.fillStyle = riskColor(level)
        ctx.fillRect(nw.x, nw.y, se.x - nw.x + 0.5, se.y - nw.y + 0.5)
      })
      canvas.style.filter = `blur(${Math.min(24, Math.max(2, cellPx * 0.35))}px)`
    }
    const hide = () => {
      if (canvasRef.current) canvasRef.current.style.visibility = 'hidden'
    }

    draw()
    map.on('moveend zoomend resize', draw)
    map.on('zoomstart', hide)
    return () => {
      map.off('moveend zoomend resize', draw)
      map.off('zoomstart', hide)
    }
  }, [map, points, levels, stepDeg])

  return null
}
