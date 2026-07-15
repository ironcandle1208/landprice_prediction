import { describe, expect, it } from 'vitest'
import {
  createPopupHtml,
  formatDeviationRate,
  formatDistance,
  formatPassengers,
  formatPopupData,
  formatPrice,
  type PredictionProperties,
} from './formatters'

const completeProperties: PredictionProperties = {
  price_yen_per_m2: 459000,
  predicted_price_yen_per_m2: 306204,
  deviation_rate: 0.499,
  station_name: '東京',
  station_distance_m: 447,
  passengers: 30916,
  use_district: '商業地域',
  floor_area_ratio: 600,
  city_code: '13101',
}

describe('数値フォーマッター', () => {
  it('金額を単位付きで整形する', () => {
    expect(formatPrice(459000)).toBe('459,000 円/m²')
    expect(formatPrice(null)).toBe('－')
  })

  it('距離を単位付きで整形する', () => {
    expect(formatDistance(1447)).toBe('1,447 m')
    expect(formatDistance(undefined)).toBe('－')
  })

  it('乗降客数を単位付きで整形する', () => {
    expect(formatPassengers(30916)).toBe('30,916 人/日')
    expect(formatPassengers(null)).toBe('－')
  })

  it('乖離率を符号と小数1桁付きで整形する', () => {
    expect(formatDeviationRate(0.499)).toBe('+49.9%')
    expect(formatDeviationRate(-0.1234)).toBe('-12.3%')
    expect(formatDeviationRate(0)).toBe('0.0%')
    expect(formatDeviationRate(null)).toBe('－')
  })
})

describe('ポップアップ整形', () => {
  it('全項目を表示用データへ整形する', () => {
    expect(formatPopupData(completeProperties)).toEqual({
      actualPrice: '459,000 円/m²',
      predictedPrice: '306,204 円/m²',
      deviationRate: '+49.9%',
      stationName: '東京',
      stationDistance: '447 m',
      passengers: '30,916 人/日',
      useDistrict: '商業地域',
      floorAreaRatio: '600%',
    })
  })

  it('nullと空文字列をダッシュへ変換する', () => {
    const emptyProperties: PredictionProperties = {
      price_yen_per_m2: null,
      predicted_price_yen_per_m2: null,
      deviation_rate: null,
      station_name: '',
      station_distance_m: null,
      passengers: null,
      use_district: null,
      floor_area_ratio: null,
    }

    expect(Object.values(formatPopupData(emptyProperties))).toEqual(
      Array(8).fill('－'),
    )
  })

  it('HTMLを生成し、データ由来文字列をエスケープする', () => {
    const html = createPopupHtml({
      ...completeProperties,
      station_name: '<東京&駅>',
    })

    expect(html).toContain('<dt>実測地価</dt><dd>459,000 円/m²</dd>')
    expect(html).toContain('&lt;東京&amp;駅&gt;')
    expect(html).not.toContain('<東京&駅>')
  })
})
