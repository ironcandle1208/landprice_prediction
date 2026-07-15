import { useEffect, useRef, useState } from 'react'
import maplibregl, {
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  type StyleSpecification,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './App.css'
import {
  createPopupHtml,
  type PredictionProperties,
} from './lib/formatters'
import {
  createPredictionCirclePaint,
  DEVIATION_COLOR_STOPS,
} from './lib/mapStyle'

const PREDICTIONS_SOURCE_ID = 'price-predictions'
const PREDICTIONS_LAYER_ID = 'price-prediction-circles'

const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    'gsi-pale': {
      type: 'raster',
      tiles: ['https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 18,
    },
  },
  layers: [
    {
      id: 'gsi-pale-layer',
      type: 'raster',
      source: 'gsi-pale',
      minzoom: 0,
    },
  ],
}

const legendGradient = `linear-gradient(to right, ${DEVIATION_COLOR_STOPS.map(
  ({ color, value }) => `${color} ${(value + 0.5) * 100}%`,
).join(', ')})`

type DataStatus = 'loading' | 'ready'

interface AboutModalProps {
  onClose: () => void
}

/** サイトの目的、出典、免責事項を表示するモーダル。 */
function AboutModal({ onClose }: AboutModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeButtonRef.current?.focus()

    /** Escapeキーでモーダルを閉じる。 */
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <section
        className="about-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="about-title"
      >
        <div className="about-modal__header">
          <div>
            <span className="about-modal__eyebrow">ABOUT</span>
            <h2 id="about-title">このサイトについて</h2>
          </div>
          <button
            ref={closeButtonRef}
            className="icon-button"
            type="button"
            aria-label="閉じる"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="about-modal__body">
          <section>
            <h3>予測データについて</h3>
            <p>
              本サイトの予測地価および乖離率は、機械学習を用いた本サイト独自の推計です。国土交通省が公表した値ではありません。
            </p>
          </section>
          <section>
            <h3>利用上の注意</h3>
            <p>
              個人の学習目的で作成したものです。不動産取引、投資、資産評価その他の重要な判断には使用しないでください。
            </p>
          </section>
          <section>
            <h3>出典</h3>
            <p>
              「国土数値情報（地価公示データ L01・駅別乗降客数データ
              S12・鉄道データ N02）」（国土交通省）を加工して作成、および
              <a
                href="https://maps.gsi.go.jp/development/ichiran.html"
                target="_blank"
                rel="noreferrer"
              >
                地理院タイル
              </a>
              を使用しています。
            </p>
          </section>
          <section>
            <h3>免責事項</h3>
            <p>
              掲載情報の正確性、完全性、最新性を保証しません。本サイトの利用によって生じた損害について、作成者は責任を負いません。
            </p>
          </section>
        </div>
      </section>
    </div>
  )
}

/** MapLibre地図と画面上の情報パネルを構成するアプリケーション。 */
function App() {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [isAboutOpen, setIsAboutOpen] = useState(false)
  const [dataStatus, setDataStatus] = useState<DataStatus>('loading')

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: MAP_STYLE,
      center: [137, 38],
      zoom: 5,
      minZoom: 3,
      maxZoom: 18,
      attributionControl: false,
    })
    mapRef.current = map

    map.addControl(
      new maplibregl.NavigationControl({
        showCompass: false,
        visualizePitch: false,
      }),
      'top-right',
    )
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: [
          '「国土数値情報（地価公示データ・駅別乗降客数データ・鉄道データ）」（国土交通省）をもとに作成',
          '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noreferrer">地理院タイル</a>',
        ],
      }),
      'bottom-right',
    )

    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '320px',
      offset: 9,
    })

    /** クリックした予測地点の属性をポップアップへ表示する。 */
    const handlePointClick = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (!feature?.properties) {
        return
      }

      const properties = feature.properties as PredictionProperties
      popup
        .setLngLat(event.lngLat)
        .setHTML(createPopupHtml(properties))
        .addTo(map)
    }

    /** circle上でクリック可能であることをカーソルで示す。 */
    const showPointerCursor = () => {
      map.getCanvas().style.cursor = 'pointer'
    }

    /** circleから離れたときに既定のカーソルへ戻す。 */
    const resetCursor = () => {
      map.getCanvas().style.cursor = ''
    }

    map.on('load', () => {
      map.addSource(PREDICTIONS_SOURCE_ID, {
        type: 'geojson',
        data: '/data/predictions.geojson',
      })
      map.addLayer({
        id: PREDICTIONS_LAYER_ID,
        type: 'circle',
        source: PREDICTIONS_SOURCE_ID,
        paint: createPredictionCirclePaint(),
      })

      map.on('click', PREDICTIONS_LAYER_ID, handlePointClick)
      map.on('mouseenter', PREDICTIONS_LAYER_ID, showPointerCursor)
      map.on('mouseleave', PREDICTIONS_LAYER_ID, resetCursor)
    })

    map.on('sourcedata', (event) => {
      if (
        event.sourceId === PREDICTIONS_SOURCE_ID &&
        event.isSourceLoaded
      ) {
        setDataStatus('ready')
      }
    })

    return () => {
      popup.remove()
      map.remove()
      mapRef.current = null
    }
  }, [])

  return (
    <main className="app-shell">
      <div
        ref={mapContainerRef}
        className="map-container"
        aria-label="予測地価と実測地価の乖離率を表示する日本地図"
      />

      <header className="map-header">
        <div className="map-header__brand" aria-hidden="true">
          <span className="brand-mark">LP</span>
        </div>
        <div className="map-header__content">
          <p className="map-header__eyebrow">LAND PRICE INSIGHT</p>
          <h1>地価予測マップ</h1>
          <p className="map-header__description">
            実測地価とAI予測地価の乖離を可視化
          </p>
          <div className={`data-status data-status--${dataStatus}`}>
            <span aria-hidden="true" />
            {dataStatus === 'ready' ? '予測地点を表示中' : '予測地点を読み込み中'}
          </div>
        </div>
        <button
          className="about-button"
          type="button"
          onClick={() => setIsAboutOpen(true)}
        >
          <span aria-hidden="true">i</span>
          このサイトについて
        </button>
      </header>

      <aside className="legend" aria-label="乖離率の凡例">
        <div className="legend__header">
          <div>
            <span className="legend__eyebrow">DEVIATION</span>
            <h2>予測地価との乖離率</h2>
          </div>
          <span className="legend__unit">%</span>
        </div>
        <div className="legend__bar" style={{ background: legendGradient }} />
        <div className="legend__ticks" aria-hidden="true">
          <span>-50</span>
          <span>0</span>
          <span>+50</span>
        </div>
        <div className="legend__labels">
          <span>割安</span>
          <span aria-hidden="true">←</span>
          <span className="legend__line" aria-hidden="true" />
          <span aria-hidden="true">→</span>
          <span>割高</span>
        </div>
      </aside>

      {isAboutOpen && <AboutModal onClose={() => setIsAboutOpen(false)} />}
    </main>
  )
}

export default App
