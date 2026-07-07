"""特徴量テーブルの生成と出力。

フルモデル用・オンライン推論用の2系統をParquetで出力する。
2系統の理由: 任意地点クリック（Phase 2の推論API）では用途地域・容積率が
取得できないため、オンラインで再現可能な特徴量のみのモデルを別途用意する。
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from landprice import columns as c
from landprice.schema import (
    FullFeatureSchema,
    OnlineFeatureSchema,
    validate_feature_frame,
)


def build_feature_tables(
    joined: gpd.GeoDataFrame, *, geographic_crs: str = "EPSG:6668"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """最寄駅結合済みデータからフル用・オンライン用の特徴量テーブルを生成する。

    - 出力行数は入力行数と一致する（行の削除・補完はしない）
    - 座標は地理座標系のlon/latとして出力する
    - 乗降客数の欠損（非公開駅等）は欠損のまま保持し、0に置換しない
    - 出力前にPydanticスキーマとカラム名・型の一致を検証する
    """
    if joined.crs is None:
        raise ValueError("CRS未設定のデータからは座標（lon/lat）を出力できません")
    gdf = joined if joined.crs.is_geographic else joined.to_crs(geographic_crs)

    full = pd.DataFrame(
        {
            c.PRICE: gdf[c.PRICE].astype("float64"),
            c.STATION_DISTANCE_M: gdf[c.STATION_DISTANCE_M].astype("float64"),
            c.PASSENGERS: gdf[c.PASSENGERS].astype("float64"),
            c.USE_DISTRICT: gdf[c.USE_DISTRICT].astype("string"),
            c.FLOOR_AREA_RATIO: gdf[c.FLOOR_AREA_RATIO].astype("float64"),
            c.CITY_CODE: gdf[c.CITY_CODE].astype("string"),
            c.STATION_GROUP_CODE: gdf[c.STATION_GROUP_CODE].astype("string"),
            c.STATION_NAME: gdf[c.STATION_NAME].astype("string"),
            c.LON: gdf.geometry.x.astype("float64"),
            c.LAT: gdf.geometry.y.astype("float64"),
        },
        index=gdf.index,
    )
    validate_feature_frame(full, FullFeatureSchema)

    online = full[list(OnlineFeatureSchema.model_fields)].copy()
    validate_feature_frame(online, OnlineFeatureSchema)
    return full, online


def write_feature_tables(
    full: pd.DataFrame, online: pd.DataFrame, out_dir: Path
) -> tuple[Path, Path]:
    """2系統の特徴量テーブルをParquetで出力し、出力パスを返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    full_path = out_dir / "features_full.parquet"
    online_path = out_dir / "features_online.parquet"
    full.to_parquet(full_path)
    online.to_parquet(online_path)
    return full_path, online_path
