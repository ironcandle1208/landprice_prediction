"""特徴量テーブル出力のテスト。

docs/plan/test/preprocessing.feature「ルール: 特徴量テーブルの出力」および
「非公開駅の欠損が後段の処理で0埋めされない」に対応。
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from landprice import columns as c
from landprice.preprocess.features import build_feature_tables, write_feature_tables
from landprice.schema import (
    FeatureSchemaError,
    FullFeatureSchema,
    OnlineFeatureSchema,
    expected_dtypes,
    validate_feature_frame,
    validate_feature_values,
)
from tests.conftest import CRS


def make_joined(n: int = 3, *, passengers_nan_at: int | None = None) -> gpd.GeoDataFrame:
    """最寄駅結合済み相当のGeoDataFrameを作る。"""
    passengers = [10000.0 + i for i in range(n)]
    if passengers_nan_at is not None:
        passengers[passengers_nan_at] = np.nan
    return gpd.GeoDataFrame(
        {
            c.PRICE: pd.array([100000.0 + i for i in range(n)], dtype="float64"),
            c.USE_DISTRICT: pd.array(
                ["商業地域" if i % 2 == 0 else None for i in range(n)], dtype="string"
            ),
            c.FLOOR_AREA_RATIO: pd.array([400.0] * n, dtype="float64"),
            c.CITY_CODE: pd.array(["13101"] * n, dtype="string"),
            c.STATION_GROUP_CODE: pd.array([f"{i:06d}" for i in range(n)], dtype="string"),
            c.STATION_NAME: pd.array([f"駅{i}" for i in range(n)], dtype="string"),
            c.PASSENGERS: pd.array(passengers, dtype="float64"),
            c.STATION_DISTANCE_M: pd.array([500.0 + i for i in range(n)], dtype="float64"),
        },
        geometry=gpd.points_from_xy(
            [139.7 + 0.001 * i for i in range(n)], [35.68] * n
        ),
        crs=CRS,
    )


def test_output_schema_matches_definition() -> None:
    """シナリオ: 出力スキーマが定義と一致する"""
    full, online = build_feature_tables(make_joined())

    # カラム名と型が定義済みスキーマ（Pydanticモデル）と一致する
    assert list(full.columns) == list(FullFeatureSchema.model_fields)
    assert list(online.columns) == list(OnlineFeatureSchema.model_fields)
    for name, dtype in expected_dtypes(FullFeatureSchema).items():
        assert str(full[name].dtype) == dtype

    # 検証関数もスキーマ不一致を検出できる（カラム欠落で例外）
    with pytest.raises(FeatureSchemaError):
        validate_feature_frame(full.drop(columns=[c.PRICE]), FullFeatureSchema)


def test_output_row_count_matches_input() -> None:
    """シナリオ: 出力行数が入力の地価地点数と一致する"""
    full, online = build_feature_tables(make_joined(100))

    assert len(full) == 100
    assert len(online) == 100


def test_parquet_roundtrip_preserves_dtypes_and_missing(tmp_path: Path) -> None:
    """シナリオ: Parquetの書き込み・読み込みで型が保持される"""
    full, online = build_feature_tables(make_joined(5, passengers_nan_at=2))

    full_path, online_path = write_feature_tables(full, online, tmp_path)
    full_read = pd.read_parquet(full_path)
    online_read = pd.read_parquet(online_path)

    # 各カラムの型は出力前と一致する
    assert [str(t) for t in full_read.dtypes] == [str(t) for t in full.dtypes]
    # 欠損（NaN）の位置も一致する
    pd.testing.assert_frame_equal(full_read.isna(), full.isna())
    pd.testing.assert_frame_equal(online_read.isna(), online.isna())


def test_two_table_variants_are_output() -> None:
    """シナリオ: フル特徴量とオンライン特徴量の2系統が出力される"""
    full, online = build_feature_tables(make_joined())

    # オンライン推論用テーブルには用途地域・容積率が含まれない
    assert c.USE_DISTRICT not in online.columns
    assert c.FLOOR_AREA_RATIO not in online.columns
    # オンライン推論用テーブルには駅距離・乗降客数が含まれる
    assert c.STATION_DISTANCE_M in online.columns
    assert c.PASSENGERS in online.columns
    # フル側には静的属性も含まれる
    assert c.USE_DISTRICT in full.columns
    assert c.FLOOR_AREA_RATIO in full.columns


def test_missing_passengers_not_filled_with_zero() -> None:
    """シナリオ: 非公開駅の欠損が後段の処理で0埋めされない"""
    full, online = build_feature_tables(make_joined(3, passengers_nan_at=1))

    # 該当駅由来の乗降客数特徴量は欠損のままであり、0に置換されない
    assert pd.isna(full[c.PASSENGERS].iloc[1])
    assert pd.isna(online[c.PASSENGERS].iloc[1])
    assert (full[c.PASSENGERS].fillna(-1) != 0).all()


@pytest.mark.parametrize(
    "column",
    [
        c.PRICE,
        c.STATION_DISTANCE_M,
        c.CITY_CODE,
        c.STATION_GROUP_CODE,
        c.STATION_NAME,
    ],
)
def test_build_feature_tables_rejects_missing_required_value(column: str) -> None:
    """シナリオ: 特徴量の必須値が欠損している場合は出力しない"""
    joined = make_joined()
    joined.loc[joined.index[0], column] = pd.NA

    with pytest.raises(FeatureSchemaError, match="必須値に欠損"):
        build_feature_tables(joined)


@pytest.mark.parametrize("invalid_price", [-1.0, np.inf])
def test_validate_feature_values_rejects_invalid_price(invalid_price: float) -> None:
    """シナリオ: 地価が負数または無限大の場合は拒否する"""
    full, _ = build_feature_tables(make_joined())
    full.loc[full.index[0], c.PRICE] = invalid_price

    with pytest.raises(FeatureSchemaError, match="地価は有限な正数"):
        validate_feature_values(full)


@pytest.mark.parametrize("invalid_distance", [-1.0, np.inf])
def test_validate_feature_values_rejects_invalid_station_distance(
    invalid_distance: float,
) -> None:
    """シナリオ: 駅距離が負数または無限大の場合は拒否する"""
    full, _ = build_feature_tables(make_joined())
    full.loc[full.index[0], c.STATION_DISTANCE_M] = invalid_distance

    with pytest.raises(FeatureSchemaError, match="駅距離は有限な0以上"):
        validate_feature_values(full)


@pytest.mark.parametrize("invalid_passengers", [-1.0, np.inf])
def test_validate_feature_values_rejects_invalid_passengers(
    invalid_passengers: float,
) -> None:
    """シナリオ: 乗降客数が負数または無限大の場合は拒否する"""
    full, _ = build_feature_tables(make_joined())
    full.loc[full.index[0], c.PASSENGERS] = invalid_passengers

    with pytest.raises(FeatureSchemaError, match="乗降客数は欠損または有限な0以上"):
        validate_feature_values(full)


@pytest.mark.parametrize(
    ("column", "invalid_value", "message"),
    [
        (c.LON, 121.9, "経度が日本の想定範囲外"),
        (c.LON, 154.1, "経度が日本の想定範囲外"),
        (c.LAT, 19.9, "緯度が日本の想定範囲外"),
        (c.LAT, 46.1, "緯度が日本の想定範囲外"),
    ],
)
def test_validate_feature_values_rejects_coordinates_outside_japan(
    column: str, invalid_value: float, message: str
) -> None:
    """シナリオ: 経度・緯度が日本の想定範囲外の場合は拒否する"""
    full, _ = build_feature_tables(make_joined())
    full.loc[full.index[0], column] = invalid_value

    with pytest.raises(FeatureSchemaError, match=message):
        validate_feature_values(full)
