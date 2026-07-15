"""モデル学習パイプラインのCLIエントリポイント。

使い方（リポジトリルートで実行する場合）:
    cd pipeline && uv run python -m landprice.train.run \
        --features-full ../data/processed/features_full.parquet \
        --features-online ../data/processed/features_online.parquet \
        --out ../data/models
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from landprice.config import TrainConfig
from landprice.schema import (
    FullFeatureSchema,
    OnlineFeatureSchema,
    validate_feature_frame,
    validate_feature_values,
)
from landprice.train.geojson import build_prediction_frame, write_predictions_geojson
from landprice.train.model import train_model


@dataclass
class TrainingPipelineResult:
    """学習パイプラインの実行結果。"""

    full_model_path: Path
    online_model_path: Path
    metrics_path: Path
    predictions_path: Path
    n_full_samples: int
    n_online_samples: int
    metrics: dict[str, object]


def run_training(
    features_full_path: Path,
    features_online_path: Path,
    out_dir: Path,
    config: TrainConfig | None = None,
) -> TrainingPipelineResult:
    """2系統の交差検証・最終学習を行い、全成果物を出力する。"""
    config = config or TrainConfig()
    full = pd.read_parquet(features_full_path)
    online = pd.read_parquet(features_online_path)

    # 前処理成果物の契約を学習入口でも検証し、カラムずれを黙って受け入れない。
    validate_feature_frame(full, FullFeatureSchema)
    validate_feature_values(full)
    validate_feature_frame(online, OnlineFeatureSchema)

    full_result = train_model(
        full,
        feature_names=config.full_features,
        categorical_features=config.full_categorical_features,
        config=config,
    )
    online_result = train_model(
        online,
        feature_names=config.online_features,
        categorical_features=config.online_categorical_features,
        config=config,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    full_model_path = out_dir / "model_full.txt"
    online_model_path = out_dir / "model_online.txt"
    metrics_path = out_dir / "metrics.json"
    predictions_path = out_dir / "predictions.geojson"

    # pickleを介さず、LambdaでLightGBM Boosterから直接読める形式に固定する。
    full_result.booster.save_model(str(full_model_path))
    online_result.booster.save_model(str(online_model_path))

    metrics: dict[str, object] = {
        "full": full_result.metrics,
        "online": online_result.metrics,
    }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    prediction_frame = build_prediction_frame(full, full_result.oof_actual_predictions)
    write_predictions_geojson(prediction_frame, predictions_path)

    return TrainingPipelineResult(
        full_model_path=full_model_path,
        online_model_path=online_model_path,
        metrics_path=metrics_path,
        predictions_path=predictions_path,
        n_full_samples=len(full),
        n_online_samples=len(online),
        metrics=metrics,
    )


def main() -> None:
    """CLI引数を解釈して学習パイプラインを実行する。"""
    parser = argparse.ArgumentParser(description="地価予測LightGBMモデルの学習パイプライン")
    parser.add_argument(
        "--features-full", type=Path, required=True, help="フル特徴量Parquetのパス"
    )
    parser.add_argument(
        "--features-online", type=Path, required=True, help="オンライン特徴量Parquetのパス"
    )
    parser.add_argument("--out", type=Path, required=True, help="学習成果物の出力ディレクトリ")
    args = parser.parse_args()

    result = run_training(args.features_full, args.features_online, args.out)
    print(f"フルモデル学習行数: {result.n_full_samples}")
    print(f"オンラインモデル学習行数: {result.n_online_samples}")
    print(f"フルモデル: {result.full_model_path}")
    print(f"オンラインモデル: {result.online_model_path}")
    print(f"評価指標: {result.metrics_path}")
    print(f"OOF予測GeoJSON: {result.predictions_path}")


if __name__ == "__main__":
    main()
