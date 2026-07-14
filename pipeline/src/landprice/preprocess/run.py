"""前処理パイプラインの実行エントリポイント。

L01（地価公示）とS12（駅別乗降客数）を読み込み、特徴量テーブル
（フル用・オンライン推論用の2系統、Parquet）と検証レポートを出力する。

使い方（リポジトリルートで実行する場合）:
    cd pipeline && uv run python -m landprice.preprocess.run \
        --l01 ../data/raw/l01/L01-26_GML/L01-26.geojson \
        --s12 ../data/raw/s12/S12-25/S12-25_GML/UTF-8/S12-25_NumberOfPassengers.geojson \
        --out ../data/processed
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from landprice import columns as c
from landprice.config import PipelineConfig
from landprice.preprocess.features import build_feature_tables, write_feature_tables
from landprice.preprocess.l01 import load_land_points
from landprice.preprocess.nearest import join_nearest_station
from landprice.preprocess.s12 import extract_passengers
from landprice.preprocess.stations import consolidate_by_group, to_points
from landprice.preprocess.validation import (
    find_distance_inconsistencies,
    find_out_of_japan_bounds,
)


@dataclass
class PipelineResult:
    """パイプラインの実行結果（出力パスと検証レポート）。"""

    full_path: Path
    online_path: Path
    n_land_points: int
    n_station_groups: int
    out_of_bounds: gpd.GeoDataFrame
    distance_inconsistencies: pd.DataFrame | None


def run_pipeline(
    l01_path: Path,
    s12_path: Path,
    out_dir: Path,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """前処理パイプラインを実行し、特徴量テーブルと検証レポートを出力する。"""
    config = config or PipelineConfig()

    # 読み込みと論理名への変換
    land = load_land_points(gpd.read_file(l01_path), config.l01_columns)
    stations_raw = extract_passengers(gpd.read_file(s12_path), config.s12)

    # 座標検証（行は削除せずレポートのみ）
    out_of_bounds = find_out_of_japan_bounds(
        land,
        lon_range=config.japan_lon_range,
        lat_range=config.japan_lat_range,
        geographic_crs=config.geographic_crs,
    )

    # 駅のポイント化 → 駅グループ名寄せ → 最寄駅結合
    stations = consolidate_by_group(to_points(stations_raw, metric_crs=config.metric_crs))
    joined = join_nearest_station(land, stations, metric_crs=config.metric_crs)

    # 特徴量テーブルの生成と出力
    full, online = build_feature_tables(joined, geographic_crs=config.geographic_crs)
    full_path, online_path = write_feature_tables(full, online, out_dir)

    # 直線距離とL01付属の道路距離の整合検証（直線距離 ≦ 道路距離 が成り立つはず）
    inconsistencies: pd.DataFrame | None = None
    if c.L01_ROAD_DISTANCE_M in joined.columns:
        joined_attrs = pd.DataFrame(joined.drop(columns="geometry"))
        inconsistencies = find_distance_inconsistencies(joined_attrs)
        if len(inconsistencies) > 0:
            inconsistencies.to_csv(out_dir / "report_distance_inconsistencies.csv", index=True)
    if len(out_of_bounds) > 0:
        pd.DataFrame(out_of_bounds.drop(columns="geometry")).to_csv(
            out_dir / "report_out_of_bounds.csv", index=True
        )

    return PipelineResult(
        full_path=full_path,
        online_path=online_path,
        n_land_points=len(land),
        n_station_groups=len(stations),
        out_of_bounds=out_of_bounds,
        distance_inconsistencies=inconsistencies,
    )


def main() -> None:
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(description="地価×駅距離×乗降客数の前処理パイプライン")
    parser.add_argument("--l01", type=Path, required=True, help="L01のGeoJSON/Shapefileパス")
    parser.add_argument("--s12", type=Path, required=True, help="S12のGeoJSON/Shapefileパス")
    parser.add_argument("--out", type=Path, required=True, help="出力ディレクトリ")
    args = parser.parse_args()

    result = run_pipeline(args.l01, args.s12, args.out)

    print(f"地価地点数: {result.n_land_points}")
    print(f"駅グループ数: {result.n_station_groups}")
    print(f"フル特徴量: {result.full_path}")
    print(f"オンライン特徴量: {result.online_path}")
    print(f"座標範囲外の地点: {len(result.out_of_bounds)}件")
    if result.distance_inconsistencies is not None:
        n_inconsistent = len(result.distance_inconsistencies)
        print(f"距離整合の要確認地点（直線距離 > 道路距離）: {n_inconsistent}件")


if __name__ == "__main__":
    main()
