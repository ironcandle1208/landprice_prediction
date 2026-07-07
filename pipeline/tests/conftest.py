"""テスト共通のフィクスチャビルダー。

テストは実データに依存せず、数行の小さなGeoDataFrameで行う
（実装計画「テスト方針」参照）。座標はJGD2011（EPSG:6668）の経度緯度。
"""

import geopandas as gpd
import pandas as pd

from landprice import columns as c

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
