"""OOF予測GeoJSONの計算・スキーマテスト。"""

from pathlib import Path

import numpy as np
import pytest

from landprice import columns as c
from landprice.schema import FeatureSchemaError, validate_prediction_frame
from landprice.train.geojson import (
    build_prediction_frame,
    calculate_deviation_rate,
    write_predictions_geojson,
)
from tests.helpers import make_synthetic_feature_tables


def test_calculate_deviation_rate() -> None:
    """乖離率を予測値基準で計算する。"""
    actual = np.array([120.0, 80.0, 100.0])
    predicted = np.array([100.0, 100.0, 100.0])

    result = calculate_deviation_rate(actual, predicted)

    np.testing.assert_allclose(result, [0.2, -0.2, 0.0])


def test_prediction_geojson_schema_accepts_valid_frame(tmp_path: Path) -> None:
    """正常な予測テーブルを検証し、GeoJSONとして出力できる。"""
    full, _ = make_synthetic_feature_tables()
    predicted = full[c.PRICE].to_numpy(dtype=np.float64) * 0.9
    frame = build_prediction_frame(full, predicted)

    validate_prediction_frame(frame)
    output_path = write_predictions_geojson(frame, tmp_path / "predictions.geojson")

    assert output_path.exists()
    assert '"type": "FeatureCollection"' in output_path.read_text(encoding="utf-8")
    # passengersの欠損は0埋めせず、GeoJSONのnullとして保持する。
    assert '"passengers": null' in output_path.read_text(encoding="utf-8")


def test_prediction_geojson_schema_rejects_missing_column() -> None:
    """必須カラムが欠落した予測テーブルを拒否する。"""
    full, _ = make_synthetic_feature_tables()
    frame = build_prediction_frame(full, full[c.PRICE].to_numpy(dtype=np.float64))

    with pytest.raises(FeatureSchemaError, match="カラム構成が不一致"):
        validate_prediction_frame(frame.drop(columns=[c.DEVIATION_RATE]))


def test_prediction_geojson_schema_rejects_infinite_deviation() -> None:
    """乖離率が有限値でない予測テーブルを拒否する。"""
    full, _ = make_synthetic_feature_tables()
    frame = build_prediction_frame(full, full[c.PRICE].to_numpy(dtype=np.float64))
    frame.loc[frame.index[0], c.DEVIATION_RATE] = np.inf

    with pytest.raises(FeatureSchemaError, match="乖離率は有限値"):
        validate_prediction_frame(frame)
