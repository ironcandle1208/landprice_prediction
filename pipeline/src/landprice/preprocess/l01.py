"""L01（地価公示）の読み込み。

L01の属性は「L01_xxx」形式の連番コードで年度により構成が変わるため、
L01ColumnMap（config.py）で論理名にマッピングして抽出する。
"""

import geopandas as gpd
import pandas as pd

from landprice import columns as c
from landprice.config import L01ColumnMap

# L01実データにおける文字列属性の欠損表現（令和8年版で確認済み）
MISSING_MARKERS = ("", "_")


def _to_float(series: pd.Series) -> pd.Series:
    """数値カラムをfloat64へ変換する。欠損表現（'_'等）はNaNにする。"""
    cleaned = series.astype("string").str.strip().replace(list(MISSING_MARKERS), pd.NA)
    return pd.to_numeric(cleaned).astype("float64")


def load_land_points(gdf: gpd.GeoDataFrame, columns: L01ColumnMap) -> gpd.GeoDataFrame:
    """L01のGeoDataFrameから必要属性を論理名で抽出する。

    - 地価（円/m²）・用途地域・容積率・市区町村コードを論理名カラムとして出力する
    - 用途地域が未設定（空文字・空白・'_'）の地点は欠損（NaN）として保持し、行は削除しない
    - 検証用のL01付属属性（最寄駅名・道路距離）はマッピングがある場合のみ付与する
    """
    use_district = gdf[columns.use_district].astype("string").str.strip()
    data = {
        c.PRICE: _to_float(gdf[columns.price]),
        c.USE_DISTRICT: use_district.replace(list(MISSING_MARKERS), pd.NA),
        c.FLOOR_AREA_RATIO: _to_float(gdf[columns.floor_area_ratio]),
        c.CITY_CODE: gdf[columns.city_code].astype("string"),
    }
    # L01付属の最寄駅情報は自前計算の直線距離の妥当性検証に使う（実装計画参照）
    if columns.station_name is not None:
        data[c.L01_STATION_NAME] = gdf[columns.station_name].astype("string")
    if columns.station_road_distance is not None:
        data[c.L01_ROAD_DISTANCE_M] = _to_float(gdf[columns.station_road_distance])

    return gpd.GeoDataFrame(data, geometry=gdf.geometry, crs=gdf.crs)
