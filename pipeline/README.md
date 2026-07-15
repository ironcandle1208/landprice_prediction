# landprice-pipeline

地価×駅距離×乗降客数の前処理・学習パイプライン。

国土数値情報の地価公示（L01）・駅別乗降客数（S12）から、
地価回帰モデル用の特徴量テーブル（フル用・オンライン推論用の2系統）を生成する。

## セットアップ

```bash
# リポジトリルートで（mise がツールバージョンを解決する）
cd pipeline
uv sync
```

## 前処理の実行

```bash
uv run python -m landprice.preprocess.run \
  --l01 ../data/raw/l01/L01-26_GML/L01-26.geojson \
  --s12 ../data/raw/s12/S12-25/S12-25_GML/UTF-8/S12-25_NumberOfPassengers.geojson \
  --out ../data/processed
```

データの取得手順・出力の説明は `../data/README.md` を参照。

## モデル学習の実行

```bash
uv run python -m landprice.train.run \
  --features-full ../data/processed/features_full.parquet \
  --features-online ../data/processed/features_online.parquet \
  --out ../data/models
```

出力: `model_full.txt`・`model_online.txt`（LightGBMネイティブ形式）、`metrics.json`（OOF評価のRMSE / R²）、`predictions.geojson`（OOF予測・乖離率付き）

### macOSでの注意（libomp）

LightGBMはOpenMPランタイム（libomp）を必要とする。Homebrew版libompが未導入の環境では、
scikit-learn同梱のlibompをライブラリパスに指定して実行する：

```bash
DYLD_LIBRARY_PATH=.venv/lib/python3.12/site-packages/sklearn/.dylibs uv run pytest
DYLD_LIBRARY_PATH=.venv/lib/python3.12/site-packages/sklearn/.dylibs uv run python -m landprice.train.run ...
```

恒久対応する場合は `brew install libomp`。

## テスト・品質チェック

```bash
uv run pytest          # テスト（docs/plan/test/preprocessing.feature がテストリスト）
uv run ruff check .    # リント
uv run mypy src tests  # 型チェック
```

## 構成

- `src/landprice/columns.py` — 論理カラム名の定義（属性コードは読み込み直後に論理名へ変換）
- `src/landprice/config.py` — 年度・カラムマッピング・学習設定（Pydantic）
- `src/landprice/schema.py` — 特徴量テーブル・予測GeoJSONのスキーマ定義と検証
- `src/landprice/preprocess/` — 前処理（S12抽出・駅名寄せ・最寄駅結合・L01読み込み・検証・出力）
- `src/landprice/train/` — モデル学習（対数変換・K-fold OOF評価・2系統LightGBM・GeoJSON出力）
