import { useMemo, useRef, useState } from 'react'
import type { Line, Model2D } from '../types/model'

type Props = { model: Model2D; selectedId: string | null; onSelect: (id: string) => void; onMove: (id: string, dx: number, dy: number) => void }

export default function CadViewer({ model, selectedId, onSelect, onMove }: Props) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number; line?: Line } | null>(null)

  const bounds = useMemo(() => {
    return { minX: 0, minY: 0, width: model.page_width, height: model.page_height }
  }, [model.page_width, model.page_height])

  const handleWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault()
    setZoom(z => Math.max(0.2, Math.min(8, z * (e.deltaY < 0 ? 1.12 : 0.89))))
  }

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.target === e.currentTarget) drag.current = { x: e.clientX, y: e.clientY }
    ;(e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId)
  }
  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!drag.current) return
    const dx = e.clientX - drag.current.x
    const dy = e.clientY - drag.current.y
    drag.current = { x: e.clientX, y: e.clientY }
    setPan(p => ({ x: p.x + dx, y: p.y + dy }))
  }
  const handlePointerUp = () => { drag.current = null }

  return (
    <div className="viewer-wrap">
      <div className="viewer-hint">Rueda: zoom · Arrastrar fondo: desplazar · Click: seleccionar línea</div>
      <svg className="cad" onWheel={handleWheel} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp}
        viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}>
        <g transform={`translate(${pan.x / 2},${pan.y / 2}) scale(${zoom})`}>
          <rect x={0} y={0} width={model.page_width} height={model.page_height} fill="#fff" stroke="#ddd" />
          {model.lines.map(line => {
            const selected = selectedId === line.id
            return <line key={line.id} x1={line.start.x} y1={line.start.y} x2={line.end.x} y2={line.end.y}
              stroke={selected ? '#d946ef' : '#111827'} strokeWidth={selected ? 2.5 / zoom : 0.8 / zoom}
              vectorEffect="non-scaling-stroke" onClick={(e) => { e.stopPropagation(); onSelect(line.id) }} />
          })}
        </g>
      </svg>
    </div>
  )
}
