import type { CircleLayerSpecification } from 'maplibre-gl'

export const DEVIATION_COLOR_STOPS = [
  { value: -0.5, color: '#2563eb' },
  { value: 0, color: '#f8fafc' },
  { value: 0.5, color: '#dc2626' },
] as const

interface RgbColor {
  red: number
  green: number
  blue: number
}

/** 数値を指定した範囲内へ収める。 */
function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}

/** 16進カラーコードをRGB値へ変換する。 */
function hexToRgb(color: string): RgbColor {
  return {
    red: Number.parseInt(color.slice(1, 3), 16),
    green: Number.parseInt(color.slice(3, 5), 16),
    blue: Number.parseInt(color.slice(5, 7), 16),
  }
}

/** RGB値を16進カラーコードへ変換する。 */
function rgbToHex(color: RgbColor): string {
  const toHex = (value: number) => Math.round(value).toString(16).padStart(2, '0')
  return `#${toHex(color.red)}${toHex(color.green)}${toHex(color.blue)}`
}

/** 2色の間を指定比率で線形補間する。 */
function interpolateColor(
  startColor: string,
  endColor: string,
  ratio: number,
): string {
  const start = hexToRgb(startColor)
  const end = hexToRgb(endColor)

  return rgbToHex({
    red: start.red + (end.red - start.red) * ratio,
    green: start.green + (end.green - start.green) * ratio,
    blue: start.blue + (end.blue - start.blue) * ratio,
  })
}

/** 乖離率を凡例や補助UIで使う連続色へ変換する。 */
export function deviationRateToColor(deviationRate: number): string {
  const normalizedRate = Number.isFinite(deviationRate)
    ? clamp(deviationRate, -0.5, 0.5)
    : 0

  if (normalizedRate <= 0) {
    return interpolateColor(
      DEVIATION_COLOR_STOPS[0].color,
      DEVIATION_COLOR_STOPS[1].color,
      (normalizedRate + 0.5) / 0.5,
    )
  }

  return interpolateColor(
    DEVIATION_COLOR_STOPS[1].color,
    DEVIATION_COLOR_STOPS[2].color,
    normalizedRate / 0.5,
  )
}

/** 乖離率とズームに連動するcircleレイヤーのpaint式を生成する。 */
export function createPredictionCirclePaint(): NonNullable<
  CircleLayerSpecification['paint']
> {
  return {
    'circle-color': [
      'interpolate',
      ['linear'],
      ['coalesce', ['to-number', ['get', 'deviation_rate']], 0],
      DEVIATION_COLOR_STOPS[0].value,
      DEVIATION_COLOR_STOPS[0].color,
      DEVIATION_COLOR_STOPS[1].value,
      DEVIATION_COLOR_STOPS[1].color,
      DEVIATION_COLOR_STOPS[2].value,
      DEVIATION_COLOR_STOPS[2].color,
    ],
    'circle-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      4,
      2,
      7,
      3.5,
      11,
      6,
      15,
      10,
    ],
    'circle-opacity': 0.82,
    'circle-stroke-color': '#ffffff',
    'circle-stroke-opacity': 0.72,
    'circle-stroke-width': [
      'interpolate',
      ['linear'],
      ['zoom'],
      5,
      0.4,
      12,
      1.2,
    ],
  }
}
