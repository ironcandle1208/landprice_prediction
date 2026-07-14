"""前処理データの検証。

検証は「行を黙って削除・修正しない」方針とし、疑わしい行を検証レポート
（DataFrame）として返す。呼び出し側でログ・保存して原因を調査する。
"""

import warnings

import geopandas as gpd
import pandas as pd

from landprice import columns as c


def find_out_of_japan_bounds(
    gdf: gpd.GeoDataFrame,
    *,
    lon_range: tuple[float, float] = (122.0, 154.0),
    lat_range: tuple[float, float] = (20.0, 46.0),
    geographic_crs: str = "EPSG:6668",
) -> gpd.GeoDataFrame:
    """日本の座標範囲外の地点を返す。該当があれば警告も発する。

    指定した地理座標系へ変換してから経緯度を検査する。範囲外の座標は
    測地系変換ミスや経度・緯度の取り違えの兆候。
    """
    if gdf.crs is None:
        raise ValueError("CRS未設定のデータは座標範囲を検証できません")

    geographic = gdf.to_crs(geographic_crs)
    if not (geographic.geometry.geom_type == "Point").all():
        raise ValueError("座標範囲検証にはPointジオメトリが必要です")

    lon = geographic.geometry.x
    lat = geographic.geometry.y
    out_of_bounds = gdf[
        (lon < lon_range[0])
        | (lon > lon_range[1])
        | (lat < lat_range[0])
        | (lat > lat_range[1])
    ]
    if len(out_of_bounds) > 0:
        warnings.warn(
            f"日本の座標範囲外の地点が{len(out_of_bounds)}件あります。"
            "座標系・データの取り違えを確認してください",
            stacklevel=2,
        )
    return out_of_bounds


def find_distance_inconsistencies(
    df: pd.DataFrame, *, tolerance_m: float = 0.0
) -> pd.DataFrame:
    """自前計算の直線距離がL01付属の道路距離を上回る（矛盾する）地点を返す。

    直線距離 ≦ 道路距離 が成り立つはずで、大きな矛盾は名寄せ・結合のバグの兆候。
    ただしL01の最寄駅と自前計算の最寄駅（駅グループ）が異なる場合や、
    投影座標系の距離歪み（沖縄等で数%）による軽微な逆転はありうるため、
    tolerance_m で許容誤差を与えて運用する。
    """
    inconsistent = df[
        df[c.STATION_DISTANCE_M] > df[c.L01_ROAD_DISTANCE_M] + tolerance_m
    ]
    return inconsistent
