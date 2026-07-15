import { describe, expect, it } from 'vitest'
import {
  createPredictionCirclePaint,
  deviationRateToColor,
} from './mapStyle'

describe('deviationRateToColor', () => {
  it('境界値を定義済みの色へ変換する', () => {
    expect(deviationRateToColor(-0.5)).toBe('#2563eb')
    expect(deviationRateToColor(0)).toBe('#f8fafc')
    expect(deviationRateToColor(0.5)).toBe('#dc2626')
  })

  it('範囲外の値を端の色へクランプする', () => {
    expect(deviationRateToColor(-1)).toBe('#2563eb')
    expect(deviationRateToColor(1)).toBe('#dc2626')
  })

  it('負側と正側の中間色を線形補間する', () => {
    expect(deviationRateToColor(-0.25)).toBe('#8faff4')
    expect(deviationRateToColor(0.25)).toBe('#ea9091')
  })

  it('非有限値は中間色として扱う', () => {
    expect(deviationRateToColor(Number.NaN)).toBe('#f8fafc')
  })
})

describe('createPredictionCirclePaint', () => {
  it('乖離率の線形補間式とズーム連動の半径式を生成する', () => {
    const paint = createPredictionCirclePaint()

    expect(paint['circle-color']).toEqual([
      'interpolate',
      ['linear'],
      ['coalesce', ['to-number', ['get', 'deviation_rate']], 0],
      -0.5,
      '#2563eb',
      0,
      '#f8fafc',
      0.5,
      '#dc2626',
    ])
    expect(paint['circle-radius']).toEqual([
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
    ])
  })
})
