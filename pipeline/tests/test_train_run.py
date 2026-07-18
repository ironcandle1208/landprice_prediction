"""学習パイプライン全体のスモークテスト。"""

import json
from pathlib import Path

import lightgbm as lgb

from landprice.config import TrainConfig
from landprice.train.run import run_training
from tests.helpers import make_synthetic_feature_tables


def test_training_pipeline_writes_all_artifacts(tmp_path: Path) -> None:
    """合成データの学習からモデル・評価・GeoJSON保存まで完走する。"""
    full, online = make_synthetic_feature_tables()
    full_path = tmp_path / "features_full.parquet"
    online_path = tmp_path / "features_online.parquet"
    output_dir = tmp_path / "models"
    full.to_parquet(full_path)
    online.to_parquet(online_path)

    result = run_training(
        full_path,
        online_path,
        output_dir,
        TrainConfig(n_splits=3, num_boost_round=5),
    )

    assert result.full_model_path.exists()
    assert result.online_model_path.exists()
    assert result.metrics_path.exists()
    assert result.predictions_path.exists()

    # pickleではなく、LightGBMネイティブ形式として再読込できることを確認する。
    assert lgb.Booster(model_file=str(result.full_model_path)).num_trees() >= 1
    assert lgb.Booster(model_file=str(result.online_model_path)).num_trees() >= 1

    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert set(metrics) == {"full", "online"}
    for model_metrics in metrics.values():
        assert set(model_metrics) == {"log_scale", "actual_scale", "n_samples", "n_splits"}
        assert set(model_metrics["log_scale"]) == {"rmse", "r2"}
        assert set(model_metrics["actual_scale"]) == {"rmse", "r2"}

    geojson = json.loads(result.predictions_path.read_text(encoding="utf-8"))
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == len(full)
