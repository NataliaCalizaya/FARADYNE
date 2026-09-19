import type { Model2D } from '../types/model'

const API = 'http://localhost:8000/api'

export async function extractPdf(file: File): Promise<Model2D> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/plano/extract`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createDxf(model: Model2D, scale: number): Promise<Blob> {
  const res = await fetch(`${API}/dxf`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, scale })
  })
  if (!res.ok) throw new Error(await res.text())
  return res.blob()
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
