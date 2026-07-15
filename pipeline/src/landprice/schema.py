"""特徴量テーブルのスキーマ定義（Pydantic）。

フィールド名は columns.py の論理カラム名と一致させること。
特徴量テーブルはこのスキーマに対してカラム名・型を検証してから出力する。
"""

import types
import typing

import numpy as np
import pandas as pd
from pydantic import BaseModel

from landprice import columns as c


class FullFeatureSchema(BaseModel):
    """フルモデル用特徴量（用途地域等、公示地点にしか存在しない属性を含む）。"""

    price_yen_per_m2: float  # 目的変数: 地価（円/m²）
    station_distance_m: float  # 最寄駅までの直線距離（メートル）
    passengers: float | None  # 最寄駅グループの乗降客数（非公開等は欠損）
    use_district: str | None  # 用途地域（未設定は欠損）
    floor_area_ratio: float | None  # 容積率（上限）
    city_code: str  # 市区町村コード
    station_group_code: str  # 最寄駅グループの重複コード
    station_name: str  # 最寄駅名（表示専用）
    lon: float  # 経度
    lat: float  # 緯度


class OnlineFeatureSchema(BaseModel):
    """オンライン推論用特徴量（任意地点クリックで再現可能なもののみ）。

    クリック地点には用途地域・容積率が存在しないため含めない。
    Phase 1の時点で2系統に分けておくことでPhase 2の推論APIの手戻りを防ぐ
    （実装計画「リスクと注意点」参照）。
    """

    price_yen_per_m2: float
    station_distance_m: float
    passengers: float | None
    lon: float
    lat: float


class PredictionGeoJsonSchema(BaseModel):
    """OOF予測を付与したGeoJSON生成前のテーブルスキーマ。"""

    price_yen_per_m2: float  # 実測地価（円/m²）
    predicted_price_yen_per_m2: float  # OOF予測地価（円/m²）
    deviation_rate: float  # （実測地価 - 予測地価）/ 予測地価
    station_name: str  # 最寄駅名（ポップアップ表示用）
    station_distance_m: float  # 最寄駅までの直線距離（メートル）
    passengers: float | None  # 乗降客数（非公開等は欠損）
    use_district: str | None  # 用途地域
    floor_area_ratio: float | None  # 容積率（上限）
    city_code: str  # 市区町村コード
    lon: float  # 経度
    lat: float  # 緯度


class FeatureSchemaError(ValueError):
    """特徴量テーブルがスキーマ定義と一致しない場合の例外。"""


def _unwrap_optional(annotation: object) -> object:
    """Optional[X]（X | None）からXを取り出す。Optionalでなければそのまま返す。"""
    if isinstance(annotation, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


# Pythonの型注釈 → pandasの期待dtype
_DTYPE_BY_TYPE: dict[object, str] = {
    float: "float64",
    str: "string",
}


def expected_dtypes(model: type[BaseModel]) -> dict[str, str]:
    """Pydanticモデルから「カラム名→pandasの期待dtype」のマップを得る。"""
    result: dict[str, str] = {}
    for name, field in model.model_fields.items():
        base_type = _unwrap_optional(field.annotation)
        if base_type not in _DTYPE_BY_TYPE:
            raise TypeError(f"未対応の型注釈です: {name}: {field.annotation}")
        result[name] = _DTYPE_BY_TYPE[base_type]
    return result


def validate_feature_frame(df: pd.DataFrame, model: type[BaseModel]) -> None:
    """特徴量テーブルのカラム名・型がスキーマ定義と一致するか検証する。

    一致しない場合は FeatureSchemaError を送出する（黙って出力しない）。
    """
    expected = expected_dtypes(model)
    problems: list[str] = []

    if list(df.columns) != list(expected):
        problems.append(
            f"カラム構成が不一致: 期待={list(expected)} 実際={list(df.columns)}"
        )
    else:
        for name, dtype in expected.items():
            actual = str(df[name].dtype)
            if actual != dtype:
                problems.append(f"型が不一致: {name} 期待={dtype} 実際={actual}")

    if problems:
        raise FeatureSchemaError(
            f"特徴量テーブルが{model.__name__}と一致しません: " + " / ".join(problems)
        )


def validate_feature_values(df: pd.DataFrame) -> None:
    """特徴量テーブルの必須値・有限性・値域を検証する。"""
    required = [
        c.PRICE,
        c.STATION_DISTANCE_M,
        c.CITY_CODE,
        c.STATION_GROUP_CODE,
        c.STATION_NAME,
        c.LON,
        c.LAT,
    ]
    missing_counts = df[required].isna().sum()
    if (missing_counts > 0).any():
        raise FeatureSchemaError(
            f"必須値に欠損があります: {missing_counts[missing_counts > 0].to_dict()}"
        )

    if not np.isfinite(df[c.PRICE]).all() or (df[c.PRICE] <= 0).any():
        raise FeatureSchemaError("地価は有限な正数である必要があります")

    if (
        not np.isfinite(df[c.STATION_DISTANCE_M]).all()
        or (df[c.STATION_DISTANCE_M] < 0).any()
    ):
        raise FeatureSchemaError("駅距離は有限な0以上の値である必要があります")

    passengers = df[c.PASSENGERS].dropna()
    if not np.isfinite(passengers).all() or (passengers < 0).any():
        raise FeatureSchemaError("乗降客数は欠損または有限な0以上の値にしてください")

    if not df[c.LON].between(122.0, 154.0).all():
        raise FeatureSchemaError("経度が日本の想定範囲外です")
    if not df[c.LAT].between(20.0, 46.0).all():
        raise FeatureSchemaError("緯度が日本の想定範囲外です")


def validate_prediction_frame(df: pd.DataFrame) -> None:
    """GeoJSON生成前のカラム・型・必須値・有限性を検証する。"""
    validate_feature_frame(df, PredictionGeoJsonSchema)

    required = [
        c.PRICE,
        c.PREDICTED_PRICE,
        c.DEVIATION_RATE,
        c.STATION_NAME,
        c.STATION_DISTANCE_M,
        c.CITY_CODE,
        c.LON,
        c.LAT,
    ]
    missing_counts = df[required].isna().sum()
    if (missing_counts > 0).any():
        raise FeatureSchemaError(
            f"GeoJSONの必須値に欠損があります: {missing_counts[missing_counts > 0].to_dict()}"
        )

    if not np.isfinite(df[c.PRICE]).all() or (df[c.PRICE] <= 0).any():
        raise FeatureSchemaError("GeoJSONの実測地価は有限な正数である必要があります")
    if (
        not np.isfinite(df[c.PREDICTED_PRICE]).all()
        or (df[c.PREDICTED_PRICE] <= 0).any()
    ):
        raise FeatureSchemaError("GeoJSONの予測地価は有限な正数である必要があります")
    if not np.isfinite(df[c.DEVIATION_RATE]).all():
        raise FeatureSchemaError("乖離率は有限値である必要があります")

    optional_numeric = [c.PASSENGERS, c.FLOOR_AREA_RATIO]
    for name in optional_numeric:
        values = df[name].dropna()
        if not np.isfinite(values).all():
            raise FeatureSchemaError(f"{name}は欠損または有限値である必要があります")

    if not df[c.LON].between(122.0, 154.0).all():
        raise FeatureSchemaError("GeoJSONの経度が日本の想定範囲外です")
    if not df[c.LAT].between(20.0, 46.0).all():
        raise FeatureSchemaError("GeoJSONの緯度が日本の想定範囲外です")
