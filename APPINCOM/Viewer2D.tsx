import React, { useEffect, useRef, useState } from 'react';
import type { Modelo2D, LineElement } from '../types';

type P = { x: number; y: number };

/**
 * El PDF viene en coordenadas de página (normalmente verticales).
 * Para visualizar la planta de forma horizontal no modificamos Modelo2D:
 * solamente rotamos su representación 90° en el visor.
 */
function rotate90(p: P, cx: number, cy: number): P {
  // Rotación antihoraria en coordenadas cartesianas.
  return { x: cy - p.y + cy, y: cx + p.x - cx };
}

function getBounds(points: P[]) {
  const xs = points.map(p => p.x);
  const ys = points.map(p => p.y);
  return {
    minX: Math.min(...xs), maxX: Math.max(...xs),
    minY: Math.min(...ys), maxY: Math.max(...ys),
  };
}

export default function Viewer2D({
  model,
  onChange,
}: {
  model: Modelo2D;
  onChange: (m: Modelo2D) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  function getTransform() {
    const c = ref.current!;
    const w = c.clientWidth;
    const h = c.clientHeight;
    const es = model.elements;
    const xs = es.flatMap(e => [e.x1, e.x2]);
    const ys = es.flatMap(e => [e.y1, e.y2]);
    if (!xs.length) return null;

    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const rotated = es.flatMap(e => [
      rotate90({ x: e.x1, y: e.y1 }, cx, cy),
      rotate90({ x: e.x2, y: e.y2 }, cx, cy),
    ]);
    const b = getBounds(rotated);
    const s = Math.min(
      (w - 60) / (b.maxX - b.minX || 1),
      (h - 60) / (b.maxY - b.minY || 1),
    ) * zoom;

    return { cx, cy, b, s };
  }

  function screenPoint(x: number, y: number) {
    const t = getTransform();
    if (!t) return { x: 0, y: 0 };
    const r = rotate90({ x, y }, t.cx, t.cy);
    return {
      x: 30 + (r.x - t.b.minX) * t.s,
      y: 30 + (r.y - t.b.minY) * t.s,
    };
  }

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d')!;
    const d = window.devicePixelRatio || 1;
    const w = c.clientWidth;
    const h = c.clientHeight;
    c.width = w * d;
    c.height = h * d;
    ctx.setTransform(d, 0, 0, d, 0, 0);
    ctx.clearRect(0, 0, w, h);

    if (!model.elements.length) return;

    for (const e of model.elements) {
      const a = screenPoint(e.x1, e.y1);
      const b = screenPoint(e.x2, e.y2);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = e.id === selected ? '#ef4444' : '#2563eb';
      ctx.lineWidth = e.id === selected ? 3 : 1;
      ctx.stroke();
    }
  }, [model.elements, selected, zoom]);

  function pick(e: React.MouseEvent<HTMLCanvasElement>) {
    const c = ref.current!;
    const r = c.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    let best: LineElement | null = null;
    let bd = 12;

    for (const q of model.elements) {
      const a = screenPoint(q.x1, q.y1);
      const b = screenPoint(q.x2, q.y2);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const t = Math.max(
        0,
        Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / (dx * dx + dy * dy || 1)),
      );
      const dd = Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy));
      if (dd < bd) {
        bd = dd;
        best = q;
      }
    }
    setSelected(best?.id || null);
  }

  function remove() {
    if (selected) {
      onChange({
        ...model,
        elements: model.elements.filter(e => e.id !== selected),
      });
      setSelected(null);
    }
  }

  return (
    <div className="viewer2d">
      <div className="viewer-toolbar">
        <button onClick={() => setZoom(z => Math.max(0.2, z / 1.2))}>−</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom(z => Math.min(5, z * 1.2))}>+</button>
        <button disabled={!selected} onClick={remove}>Eliminar línea</button>
      </div>
      <canvas ref={ref} onClick={pick} />
    </div>
  );
}
