"""駅ジオメトリのポイント化と駅グループ単位の名寄せ。

S12の駅はライン（ホーム形状）で提供されるため重心でポイント化する。
名寄せは駅グループ単位（確定方針）：S12の重複コードをキーにgroupbyし、
乗降客数はグループ合算する。駅名は表示専用とし、識別には重複コードを使う。
"""

import geopandas as gpd

from landprice import columns as c


def to_points(gdf: gpd.GeoDataFrame, *, metric_crs: str = "EPSG:6691") -> gpd.GeoDataFrame:
    """指定したメートル座標系で駅形状の重心を計算する。

    入力CRSの種類にかかわらず、投影座標系（metric_crs）で重心を計算してから
    元のCRSへ戻す。これにより、入力CRSによる計算結果の差異を防ぐ。
    """
    if gdf.crs is None:
        raise ValueError("駅データにCRSが設定されていません")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError("駅ジオメトリに欠損または空形状があります")

    projected = gdf.to_crs(metric_crs)
    out = gdf.copy()
    out.geometry = projected.geometry.centroid.to_crs(gdf.crs)
    return out


def consolidate_by_group(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """重複コード（駅グループ）単位で名寄せし、乗降客数をグループ合算する。

    - 同一重複コードの複数事業者レコードは1レコードに統合される
    - 同名でも重複コードが異なる駅（例: 広島と東京の「府中」）は統合されない
    - 乗降客数の合算は欠損を除いた値で行い（min_count=1）、
      全レコード欠損の場合のみ欠損とする。欠損を0扱いで合算すると
      非公開駅の集客力を過小評価するため
    - 駅名は表示専用としてグループ先頭レコードの値を採用する
    - 代表ジオメトリはグループ内ポイントの重心とする
    """
    if not (gdf.geometry.geom_type == "Point").all():
        raise ValueError("名寄せの前に to_points で駅ジオメトリをポイント化してください")

    work = gdf.assign(_x=gdf.geometry.x, _y=gdf.geometry.y)
    agg = (
        work.groupby(c.STATION_GROUP_CODE, sort=True)
        .agg(
            **{
                c.STATION_NAME: (c.STATION_NAME, "first"),
                c.PASSENGERS: (c.PASSENGERS, lambda s: s.sum(min_count=1)),
                "_x": ("_x", "mean"),
                "_y": ("_y", "mean"),
            }
        )
        .reset_index()
    )
    geometry = gpd.points_from_xy(agg["_x"], agg["_y"])
    return gpd.GeoDataFrame(
        agg.drop(columns=["_x", "_y"]), geometry=geometry, crs=gdf.crs
    )
