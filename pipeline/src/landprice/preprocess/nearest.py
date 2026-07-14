"""最寄駅の結合（sjoin_nearest）。

各地価ポイントに最寄駅（名寄せ済みの駅グループ）と直線距離を付与する。
駅距離はL01付属の「道路距離」ではなくN02/S12由来の直線距離を自前計算する。
道路距離は推論API（任意地点）で再現できず、学習時と推論時で特徴量の定義を
一致させる必要があるため（実装計画参照）。
"""

import geopandas as gpd

from landprice import columns as c


def join_nearest_station(
    land: gpd.GeoDataFrame,
    stations: gpd.GeoDataFrame,
    *,
    metric_crs: str = "EPSG:6691",
) -> gpd.GeoDataFrame:
    """各地価ポイントに最寄駅と直線距離（メートル）を付与する。

    - 距離は投影座標系（metric_crs）に変換した上でメートル単位で計算する
    - 等距離の駅が複数ある場合は重複コード順で先頭の1駅を採用し、結果を再現可能にする
    - 出力の行数・インデックス・CRSは入力の地価データと一致する
    """
    if land.empty:
        raise ValueError("地価データが0件です")
    if stations.empty:
        raise ValueError("対象年度に利用可能な駅データが0件です")
    if land.geometry.isna().any() or stations.geometry.isna().any():
        raise ValueError("ジオメトリが欠損しています")
    if land.crs is None or stations.crs is None:
        raise ValueError("CRS未設定のデータは距離計算できません。CRSを設定してください")
    if not land.index.is_unique:
        raise ValueError("地価データのインデックスが一意ではありません")

    land_m = land.to_crs(metric_crs)
    # 結合で付与するのは駅の識別・表示・特徴量カラムのみ
    stations_m = stations.to_crs(metric_crs)[
        [c.STATION_GROUP_CODE, c.STATION_NAME, c.PASSENGERS, "geometry"]
    ]

    joined = gpd.sjoin_nearest(
        land_m, stations_m, how="left", distance_col=c.STATION_DISTANCE_M
    )
    # 完全に等距離の駅が複数あると行が複製されるため、
    # 重複コード順で先頭の1駅のみ残して再現性を保証する
    joined = (
        joined.rename_axis("_land_index")
        .reset_index()
        .sort_values(["_land_index", c.STATION_GROUP_CODE], kind="stable")
        .drop_duplicates("_land_index", keep="first")
        .set_index("_land_index")
        .rename_axis(land.index.name)
    )
    joined = joined.drop(columns=["index_right"], errors="ignore")

    if len(joined) != len(land):
        raise AssertionError(
            f"最寄駅結合で行数が変化しました: {len(land)} -> {len(joined)}"
        )
    return joined.to_crs(land.crs)
