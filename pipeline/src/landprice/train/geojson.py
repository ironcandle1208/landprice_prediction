"""OOF予測と乖離率を付与したGeoJSONの生成。"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from landprice import columns as c
from landprice.schema import PredictionGeoJsonSchema, validate_prediction_frame


def calculate_deviation_rate(
    actual: ArrayLike, predicted: ArrayLike
) -> NDArray[np.float64]:
    """実測値と予測値から（実測 - 予測）/ 予測を計算する。"""
    actual_array = np.asarray(actual, dtype=np.float64)
    predicted_array = np.asarray(predicted, dtype=np.float64)
    if actual_array.shape != predicted_array.shape:
        raise ValueError("実測値と予測値の形状が一致していません")
    if not np.isfinite(actual_array).all():
        raise ValueError("実測値は有限値である必要があります")
    if not np.isfinite(predicted_array).all() or (predicted_array <= 0).any():
        raise ValueError("予測値は有限な正数である必要があります")
    deviation = (actual_array - predicted_array) / predicted_array
    if not np.isfinite(deviation).all():
        raise ValueError("乖離率が有限値になりません")
    return deviation


def build_prediction_frame(
    full_features: pd.DataFrame, predicted_prices: ArrayLike
) -> pd.DataFrame:
    """フル特徴量とOOF予測からGeoJSON生成前テーブルを構築する。"""
    predicted = np.asarray(predicted_prices, dtype=np.float64)
    if len(predicted) != len(full_features):
        raise ValueError("特徴量と予測値の行数が一致していません")
    actual = full_features[c.PRICE].to_numpy(dtype=np.float64)

    frame = pd.DataFrame(
        {
            c.PRICE: pd.array(actual, dtype="float64"),
            c.PREDICTED_PRICE: pd.array(predicted, dtype="float64"),
            c.DEVIATION_RATE: pd.array(
                calculate_deviation_rate(actual, predicted), dtype="float64"
            ),
            c.STATION_NAME: full_features[c.STATION_NAME].astype("string"),
            c.STATION_DISTANCE_M: full_features[c.STATION_DISTANCE_M].astype("float64"),
            c.PASSENGERS: full_features[c.PASSENGERS].astype("float64"),
            c.USE_DISTRICT: full_features[c.USE_DISTRICT].astype("string"),
            c.FLOOR_AREA_RATIO: full_features[c.FLOOR_AREA_RATIO].astype("float64"),
            c.CITY_CODE: full_features[c.CITY_CODE].astype("string"),
            c.LON: full_features[c.LON].astype("float64"),
            c.LAT: full_features[c.LAT].astype("float64"),
        },
        index=full_features.index,
    )
    # 出力直前だけでなく構築時にも検証し、不正データを早い段階で検出する。
    validate_prediction_frame(frame)
    return frame


def _json_value(value: object) -> object:
    """pandas・NumPyの値を厳密なJSONへ変換可能な値に正規化する。"""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_predictions_geojson(frame: pd.DataFrame, output_path: Path) -> Path:
    """検証済み予測テーブルをPoint FeatureCollectionとして出力する。"""
    validate_prediction_frame(frame)
    property_names = [
        name for name in PredictionGeoJsonSchema.model_fields if name not in {c.LON, c.LAT}
    ]
    features: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        properties = {name: _json_value(record[name]) for name in property_names}
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(record[c.LON]), float(record[c.LAT])],
                },
                "properties": properties,
            }
        )

    collection: dict[str, object] = {"type": "FeatureCollection", "features": features}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=Falseにより、欠損をnullへ変換し忘れた場合も不正JSONを出力しない。
    output_path.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output_path
