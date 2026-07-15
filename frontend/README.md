# 地価予測マップ フロントエンド

実測地価と機械学習による予測地価の乖離率（割安・割高）を日本地図上で可視化するWebアプリ。

- React + TypeScript + Vite + MapLibre GL JS
- 背景地図は国土地理院の淡色地図タイル
- 実装計画は `../docs/plan/implementation-plan.md` の「Phase 1 タスク4」を参照

## セットアップ

Node.jsはリポジトリルートの `mise.toml` で固定している（node 24）。

```bash
npm install
```

### データの配置

地図に表示する予測データはGit管理外のため、学習パイプラインの成果物を手動でコピーする（`public/data/` は `.gitignore` 済み）。

```bash
cp ../data/models/predictions.geojson public/data/predictions.geojson
```

成果物の生成方法は `../pipeline/README.md` を参照。

## コマンド

| コマンド          | 内容                                       |
| ----------------- | ------------------------------------------ |
| `npm run dev`     | 開発サーバー起動                           |
| `npm run build`   | 型チェック（tsc -b）+ 本番ビルド（dist/） |
| `npm test`        | vitestによる単体テスト                     |
| `npm run lint`    | oxlintによる静的チェック                   |
| `npm run preview` | ビルド成果物のローカル確認                 |

## 構成の要点

- `src/App.tsx` — MapLibre地図の初期化・凡例・「このサイトについて」モーダル
- `src/lib/formatters.ts` — ポップアップ表示用の整形純関数（テスト対象）
- `src/lib/mapStyle.ts` — 乖離率→色変換とcircleレイヤーのpaint式生成（テスト対象）
- 地図描画そのものはテスト対象外（実装計画の「テスト方針」参照）

## 備考

- 乖離率 = (実測地価 − 予測地価) / 予測地価。負（割安）= 青、正（割高）= 赤で表示
- `predictions.geojson` は約14MB。PMTiles化はPhase 1では見送り（配信時のgzip/brotli圧縮で実用域のため）。判断の詳細は実装計画を参照
