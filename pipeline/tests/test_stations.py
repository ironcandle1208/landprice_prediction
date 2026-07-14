"""駅ジオメトリの処理と名寄せのテスト。

docs/plan/test/preprocessing.feature「ルール: 駅ジオメトリの処理と名寄せ」に対応。
"""

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, MultiLineString, Point

from landprice import columns as c
from landprice.preprocess.stations import consolidate_by_group, to_points
from tests.conftest import CRS


def make_extracted(
    rows: Sequence[tuple[str, str, float | None, float, float]],
) -> gpd.GeoDataFrame:
    """抽出済み（論理カラム名）の駅ポイントを作る。

    rows: (駅名, 重複コード, 乗降客数, 経度, 緯度)
    """
    return gpd.GeoDataFrame(
        {
            c.STATION_NAME: pd.array([r[0] for r in rows], dtype="string"),
            c.STATION_GROUP_CODE: pd.array([r[1] for r in rows], dtype="string"),
            c.PASSENGERS: pd.array([r[2] for r in rows], dtype="float64"),
        },
        geometry=[Point(r[3], r[4]) for r in rows],
        crs=CRS,
    )


def test_linestring_converted_to_centroid_point() -> None:
    """シナリオ: ライン形状の駅が重心ポイントに変換される"""
    line = LineString([(139.700, 35.680), (139.702, 35.680)])
    gdf = gpd.GeoDataFrame({"name": ["東京"]}, geometry=[line], crs=CRS)

    out = to_points(gdf)

    assert out.geometry.iloc[0].geom_type == "Point"
    # 座標は元のラインの重心と一致する
    assert out.geometry.iloc[0].x == pytest.approx(139.701)
    assert out.geometry.iloc[0].y == pytest.approx(35.680)


def test_multilinestring_converted_to_point() -> None:
    """シナリオ: MultiLineString形状の駅も重心ポイントに変換される"""
    multi = MultiLineString(
        [[(139.700, 35.680), (139.701, 35.680)], [(139.702, 35.681), (139.703, 35.681)]]
    )
    gdf = gpd.GeoDataFrame({"name": ["大手町"]}, geometry=[multi], crs=CRS)

    out = to_points(gdf)

    assert out.geometry.iloc[0].geom_type == "Point"


def test_to_points_rejects_missing_crs() -> None:
    """CRS未設定の駅データは重心計算前に拒否する。"""
    line = LineString([(139.700, 35.680), (139.702, 35.680)])
    gdf = gpd.GeoDataFrame({"name": ["東京"]}, geometry=[line])

    with pytest.raises(ValueError, match="CRSが設定されていません"):
        to_points(gdf)


@pytest.mark.parametrize("geometry", [None, Point()])
def test_to_points_rejects_missing_or_empty_geometry(geometry: Point | None) -> None:
    """欠損または空形状の駅ジオメトリは明示的に拒否する。"""
    gdf = gpd.GeoDataFrame({"name": ["東京"]}, geometry=[geometry], crs=CRS)

    with pytest.raises(ValueError, match="欠損または空形状"):
        to_points(gdf)


def test_to_points_uses_metric_crs_for_projected_input() -> None:
    """投影座標系の入力でも指定したmetric_crs上で重心を計算する。"""
    line = LineString([(130.0, 30.0), (140.0, 35.0), (145.0, 45.0)])
    source = gpd.GeoDataFrame({"name": ["広域駅"]}, geometry=[line], crs=CRS).to_crs("EPSG:6691")
    expected = source.to_crs("EPSG:3857").geometry.centroid.to_crs(source.crs).iloc[0]
    source_crs_centroid = source.geometry.centroid.iloc[0]

    out = to_points(source, metric_crs="EPSG:3857")

    assert out.crs == source.crs
    assert out.geometry.iloc[0].equals_exact(expected, tolerance=1e-6)
    # 入力CRS上で直接求めた重心とは異なることを確認し、投影処理の省略を検出する。
    assert out.geometry.iloc[0].distance(source_crs_centroid) > 0.01


def test_same_group_code_consolidated_with_summed_passengers() -> None:
    """シナリオ: 複数事業者の同名駅が重複コードで1レコードに名寄せされる"""
    # 東京メトロ・都営・（例示として）東西線の「大手町」3事業者レコード
    gdf = make_extracted(
        [
            ("大手町", "001132", 100000.0, 139.766, 35.685),
            ("大手町", "001132", 200000.0, 139.767, 35.686),
            ("大手町", "001132", 300000.0, 139.765, 35.684),
        ]
    )

    out = consolidate_by_group(gdf)

    assert len(out) == 1
    # 乗降客数は3件の合算値である
    assert out[c.PASSENGERS].iloc[0] == 600000.0


def test_same_name_different_group_code_not_merged() -> None:
    """シナリオ: 同名でも重複コードが異なる駅は統合されない"""
    # 広島県の「府中」と東京都の「府中」
    gdf = make_extracted(
        [
            ("府中", "004201", 5000.0, 132.505, 34.393),
            ("府中", "007301", 30000.0, 139.480, 35.672),
        ]
    )

    out = consolidate_by_group(gdf)

    assert len(out) == 2
    assert (out[c.STATION_NAME] == "府中").all()


def test_consolidated_count_equals_unique_group_codes() -> None:
    """シナリオ: 名寄せ後の駅数は重複コードのユニーク数と一致する"""
    # 重複コード10種類・合計25レコード
    rows = [
        (f"駅{i % 10}", f"{i % 10:06d}", 1000.0, 139.0 + 0.01 * i, 35.0 + 0.01 * i)
        for i in range(25)
    ]
    gdf = make_extracted(rows)

    out = consolidate_by_group(gdf)

    assert len(out) == 10


def test_sum_with_missing_passengers_uses_available_values() -> None:
    """シナリオ: 乗降客数が欠損の駅を含む名寄せで合算結果が壊れない

    方針: 欠損は0扱いで合算せず、欠損を除いた合算値とする（全件欠損のみ欠損）。
    """
    gdf = make_extracted(
        [
            ("駅X", "000010", np.nan, 139.700, 35.680),
            ("駅X", "000010", 400.0, 139.701, 35.681),
        ]
    )

    out = consolidate_by_group(gdf)

    # 合算値は欠損でない側の値になる
    assert out[c.PASSENGERS].iloc[0] == 400.0


def test_consolidate_requires_point_geometry() -> None:
    """名寄せはポイント化済みデータを前提とし、ライン混在は明示的に拒否する（追加テスト）"""
    line = LineString([(139.700, 35.680), (139.702, 35.680)])
    gdf = gpd.GeoDataFrame(
        {
            c.STATION_NAME: pd.array(["東京"], dtype="string"),
            c.STATION_GROUP_CODE: pd.array(["000001"], dtype="string"),
            c.PASSENGERS: pd.array([100.0], dtype="float64"),
        },
        geometry=[line],
        crs=CRS,
    )

    with pytest.raises(ValueError, match="ポイント化"):
        consolidate_by_group(gdf)
