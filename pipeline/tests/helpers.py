"""テスト共通のデータビルダー。

テストは実データに依存せず、数行の小さなGeoDataFrameで行う
（実装計画「テスト方針」参照）。座標はJGD2011（EPSG:6668）の経度緯度。
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from landprice import columns as c
from landprice.schema import OnlineFeatureSchema

# テストデータの地理座標系（JGD2011）
CRS = "EPSG:6668"


def make_stations(rows: list[tuple[str, str, float, float, float]]) -> gpd.GeoDataFrame:
    """名寄せ済み駅ポイントのGeoDataFrameを作る。

    rows: (重複コード, 駅名, 乗降客数, 経度, 緯度)
    """
    return gpd.GeoDataFrame(
        {
            c.STATION_GROUP_CODE: pd.array([r[0] for r in rows], dtype="string"),
            c.STATION_NAME: pd.array([r[1] for r in rows], dtype="string"),
            c.PASSENGERS: pd.array([r[2] for r in rows], dtype="float64"),
        },
        geometry=gpd.points_from_xy([r[3] for r in rows], [r[4] for r in rows]),
        crs=CRS,
    )


def make_land(coords: list[tuple[float, float]]) -> gpd.GeoDataFrame:
    """地価ポイントのGeoDataFrameを作る。coords: (経度, 緯度)"""
    return gpd.GeoDataFrame(
        {"point_id": list(range(len(coords)))},
        geometry=gpd.points_from_xy([xy[0] for xy in coords], [xy[1] for xy in coords]),
        crs=CRS,
    )


def make_synthetic_feature_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """学習スモークテスト用の小さなフル・オンライン特徴量を作る。"""
    n_rows = 36
    positions = np.arange(n_rows, dtype=np.float64)
    station_distance = 100.0 + positions * 35.0
    passengers = 5000.0 + positions * 800.0
    passengers[::9] = np.nan  # 非公開駅を想定し、欠損のまま学習へ渡す。
    use_district = ["商業地域" if i % 2 == 0 else "第一種住居地域" for i in range(n_rows)]
    city_code = ["13101" if i % 3 == 0 else "13102" for i in range(n_rows)]
    prices = (
        180000.0
        + positions * 4500.0
        + np.where(np.arange(n_rows) % 2 == 0, 70000.0, 0.0)
    )

    full = pd.DataFrame(
        {
            c.PRICE: pd.array(prices, dtype="float64"),
            c.STATION_DISTANCE_M: pd.array(station_distance, dtype="float64"),
            c.PASSENGERS: pd.array(passengers, dtype="float64"),
            c.USE_DISTRICT: pd.array(use_district, dtype="string"),
            c.FLOOR_AREA_RATIO: pd.array(
                [400.0 if i % 2 == 0 else 200.0 for i in range(n_rows)],
                dtype="float64",
            ),
            c.CITY_CODE: pd.array(city_code, dtype="string"),
            c.STATION_GROUP_CODE: pd.array(
                [f"group-{i:03d}" for i in range(n_rows)], dtype="string"
            ),
            c.STATION_NAME: pd.array(
                [f"テスト駅{i % 6}" for i in range(n_rows)], dtype="string"
            ),
            c.LON: pd.array(139.5 + positions * 0.001, dtype="float64"),
            c.LAT: pd.array(35.5 + positions * 0.001, dtype="float64"),
        }
    )
    online = full[list(OnlineFeatureSchema.model_fields)].copy()
    return full, online
