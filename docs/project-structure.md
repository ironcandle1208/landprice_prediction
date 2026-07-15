# プロジェクト構造

最終更新: 2026-07-15

```
landprice_prediction/
├── .gitignore                 # Git除外設定（data/・.venv・tfstate等）
├── CLAUDE.md                  # Claude Code向けプロジェクト指示
├── AGENTS.md                  # エージェント向け指示
├── mise.toml                  # ツールバージョン固定（uv・node）
├── data/                      # Git管理外。取得手順は data/README.md 参照
│   ├── README.md              # データの出典・取得URL・前処理の実行手順
│   ├── raw/                   # 国土数値情報のダウンロード物（L01-26 / S12-24,25 / N02-25）
│   ├── processed/             # 特徴量テーブル（Parquet）と検証レポート
│   └── models/                # 学習成果物（モデル2系統・metrics.json・predictions.geojson）
├── pipeline/                  # 前処理・学習パイプライン（Python / uv管理）
│   ├── pyproject.toml         # 依存・Ruff・mypy・pytest設定
│   ├── README.md              # セットアップとコマンド
│   ├── src/landprice/
│   │   ├── columns.py         # 論理カラム名の定義
│   │   ├── config.py          # 年度・属性コードマッピング等の設定（Pydantic）
│   │   ├── schema.py          # 特徴量テーブルのスキーマ定義・検証
│   │   ├── preprocess/
│   │   │   ├── s12.py         # S12対象年度カラム抽出（データ有無・重複コード処理）
│   │   │   ├── stations.py    # 駅ポイント化・駅グループ名寄せ
│   │   │   ├── nearest.py     # 最寄駅結合（sjoin_nearest・距離計算）
│   │   │   ├── l01.py         # L01読み込み（属性コード→論理名）
│   │   │   ├── validation.py  # 座標範囲・距離整合の検証レポート
│   │   │   ├── features.py    # 特徴量テーブル生成・Parquet出力（フル/オンライン2系統）
│   │   │   └── run.py         # 前処理実行エントリポイント（CLI）
│   │   └── train/
│   │       ├── target.py      # 目的変数の対数変換・逆変換
│   │       ├── model.py       # K-fold OOF学習・評価・全データ再学習（LightGBM 2系統）
│   │       ├── geojson.py     # OOF予測・乖離率付きGeoJSON生成
│   │       └── run.py         # 学習実行エントリポイント（CLI）
│   └── tests/                 # pytest（前処理は preprocessing.feature のシナリオと1対1対応）
└── docs/
    ├── project-structure.md   # 本ファイル
    ├── data-structure.md      # データモデル（L01・S12・N02と生成物のER図・属性仕様）
    ├── issue/
    │   └── template.md        # イシュー記録のテンプレート
    ├── review/
    │   └── 20260710-codex-review.md   # 前処理パイプライン（c537682）のCodexレビュー結果
    └── plan/
        ├── template.md              # 開発計画のテンプレート
        ├── implementation-plan.md   # 実装計画（地価×駅距離×乗降客数 分析・予測マップ）
        └── test/
            ├── preprocessing.feature   # 前処理のテストシナリオ（Gherkin・設計ドキュメント）
            └── inference-api.feature   # 推論APIのテストシナリオ（Gherkin・設計ドキュメント）
```

## 備考

- `test/` 配下の `.feature` ファイルは実行しない設計ドキュメント。pytestのテストリストとして使用する（詳細は実装計画の「テスト方針」参照）
- Phase 1のうち前処理・モデル学習パイプラインは実装済み（実データで実行確認済み。OOF評価: フル対数R²=0.918、オンライン対数R²=0.849）。フロントエンド・公開（S3 + CloudFront）は未着手
- macOSでLightGBMを実行する場合はlibompが必要（回避策は `pipeline/README.md` 参照）
- Python実行は `cd pipeline && uv run ...`。品質チェックは `uv run pytest` / `uv run ruff check .` / `uv run mypy src tests`
