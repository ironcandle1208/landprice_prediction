export interface PredictionProperties {
  price_yen_per_m2: number | null
  predicted_price_yen_per_m2: number | null
  deviation_rate: number | null
  station_name: string | null
  station_distance_m: number | null
  passengers: number | null
  use_district: string | null
  floor_area_ratio: number | null
  city_code?: string | null
}

export interface PopupDisplayData {
  actualPrice: string
  predictedPrice: string
  deviationRate: string
  stationName: string
  stationDistance: string
  passengers: string
  useDistrict: string
  floorAreaRatio: string
}

const EMPTY_VALUE = '－'

/** 数値として表示できる有限値かを判定する。 */
function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** 金額を日本語の桁区切りと単位付きで整形する。 */
export function formatPrice(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) {
    return EMPTY_VALUE
  }

  return `${Math.round(value).toLocaleString('ja-JP')} 円/m²`
}

/** 駅までの距離を日本語の桁区切りと単位付きで整形する。 */
export function formatDistance(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) {
    return EMPTY_VALUE
  }

  return `${Math.round(value).toLocaleString('ja-JP')} m`
}

/** 乗降客数を日本語の桁区切りと単位付きで整形する。 */
export function formatPassengers(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) {
    return EMPTY_VALUE
  }

  return `${Math.round(value).toLocaleString('ja-JP')} 人/日`
}

/** 乖離率を符号付きのパーセント表記に整形する。 */
export function formatDeviationRate(
  value: number | null | undefined,
): string {
  if (!isFiniteNumber(value)) {
    return EMPTY_VALUE
  }

  const percentage = value * 100
  // 丸め後の -0.0 表示を防ぎ、ゼロは符号なしで表示する。
  const normalized = Math.abs(percentage) < 0.05 ? 0 : percentage
  const sign = normalized > 0 ? '+' : ''
  return `${sign}${normalized.toLocaleString('ja-JP', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`
}

/** 容積率をパーセント表記に整形する。 */
export function formatFloorAreaRatio(
  value: number | null | undefined,
): string {
  if (!isFiniteNumber(value)) {
    return EMPTY_VALUE
  }

  return `${value.toLocaleString('ja-JP', {
    maximumFractionDigits: 1,
  })}%`
}

/** nullや空文字列を画面表示用のダッシュへ変換する。 */
function formatText(value: string | null | undefined): string {
  const trimmed = value?.trim()
  return trimmed ? trimmed : EMPTY_VALUE
}

/** GeoJSONのpropertiesをポップアップ表示用データへ変換する。 */
export function formatPopupData(
  properties: PredictionProperties,
): PopupDisplayData {
  return {
    actualPrice: formatPrice(properties.price_yen_per_m2),
    predictedPrice: formatPrice(properties.predicted_price_yen_per_m2),
    deviationRate: formatDeviationRate(properties.deviation_rate),
    stationName: formatText(properties.station_name),
    stationDistance: formatDistance(properties.station_distance_m),
    passengers: formatPassengers(properties.passengers),
    useDistrict: formatText(properties.use_district),
    floorAreaRatio: formatFloorAreaRatio(properties.floor_area_ratio),
  }
}

/** HTMLへ埋め込む文字列をエスケープし、データ由来のHTML解釈を防ぐ。 */
function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    }
    return entities[character] ?? character
  })
}

/** 表示用データからMapLibreポップアップ用HTMLを生成する。 */
export function createPopupHtml(properties: PredictionProperties): string {
  const data = formatPopupData(properties)
  const rows: ReadonlyArray<readonly [string, string]> = [
    ['実測地価', data.actualPrice],
    ['予測地価', data.predictedPrice],
    ['乖離率', data.deviationRate],
    ['最寄駅', data.stationName],
    ['駅距離', data.stationDistance],
    ['乗降客数', data.passengers],
    ['用途地域', data.useDistrict],
    ['容積率', data.floorAreaRatio],
  ]

  const rowHtml = rows
    .map(
      ([label, value]) =>
        `<div class="popup-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`,
    )
    .join('')

  return `<section class="price-popup" aria-label="地点の地価情報"><h2>地点情報</h2><dl>${rowHtml}</dl></section>`
}
