export type Point = { x: number; y: number }
export type Line = {
  id: string
  type: 'LINE'
  start: Point
  end: Point
  page: number
  source: string
  confidence: number
}
export type TextItem = { text: string; x: number; y: number; width: number; height: number }
export type Model2D = {
  units: string
  page_width: number
  page_height: number
  lines: Line[]
  texts: TextItem[]
  levels: number[]
}
