"""S12除外〜最寄駅結合までを直列につないだ統合テスト。

docs/plan/test/preprocessing.feature「ルール: S12の対象年度カラム抽出」の
「廃止駅より営業中の駅が最寄駅として選ばれる（統合）」シナリオに対応。

extract_passengers（S12の駅なし除外）→ to_points（ポイント化）→
consolidate_by_group（駅グループ名寄せ）→ join_nearest_station（最寄駅結合）を
実際に直列で実行し、地価地点のすぐ近くに廃止駅があっても、
やや離れた営業中の駅が最寄駅として選ばれることを検証する。
修正前のextract_passengers（駅なしレコードを除外しない実装）ではこのテストは失敗する
（廃止駅の座標が駅グループの重心計算に混入し、廃止駅が最寄駅として選ばれてしまう）。
"""

import geopandas as gpd
from shapely.geometry import LineString

from landprice import columns as c
from landprice.config import S12Config, S12DataStatus, S12Duplicate
from landprice.preprocess.nearest import join_nearest_station
from landprice.preprocess.s12 import extract_passengers
from landprice.preprocess.stations import consolidate_by_group, to_points
from tests.helpers import CRS, make_land


def make_s12_raw_with_coords(
    rows: list[tuple[str, str, int, int, float, tuple[float, float], tuple[float, float]]],
) -> gpd.GeoDataFrame:
    """座標を行ごとに指定できるS12の生データ形式（2022〜2024年度が横に並ぶ）を作る。

    test_s12.pyのmake_s12_rawは全行同一座標のため、駅ごとに異なる座標を
    配置する本テストでは使えず、ここに個別のヘルパーを新設する。

    rows: (駅名, グループコード, 重複コード2024, データ有無コード2024, 乗降客数2024,
           ラインの始点(経度, 緯度), ラインの終点(経度, 緯度))
    """
    n = len(rows)
    data: dict[str, list[object]] = {
        "S12_001": [r[0] for r in rows],  # 駅名
        "S12_001c": [r[1] for r in rows],  # 駅コード
        "S12_001g": [r[1] for r in rows],  # グループコード
        # 2022年度（S12_050〜053）: 対象年度ではないためダミー値
        "S12_050": [1] * n,
        "S12_051": [1] * n,
        "S12_052": [""] * n,
        "S12_053": [111.0] * n,
        # 2023年度（S12_054〜057）: 対象年度ではないためダミー値
        "S12_054": [1] * n,
        "S12_055": [1] * n,
        "S12_056": [""] * n,
        "S12_057": [222.0] * n,
        # 2024年度（S12_058〜061）
        "S12_058": [r[2] for r in rows],
        "S12_059": [r[3] for r in rows],
        "S12_060": [""] * n,
        "S12_061": [r[4] for r in rows],
    }
    geometry = [LineString([r[5], r[6]]) for r in rows]
    return gpd.GeoDataFrame(data, geometry=geometry, crs=CRS)


def test_active_station_chosen_over_closer_abolished_station() -> None:
    """シナリオ: 廃止駅より営業中の駅が最寄駅として選ばれる（統合）"""
    # 地価地点（東京駅の北約500mを想定した座標）
    land_point = (139.7671, 35.6857)
    land = make_land([land_point])

    # 地価地点のすぐ近く（約10m）に廃止駅（データ有無コード=駅なし）を配置。
    # グループコードは営業中駅と別にする
    abolished_start = (139.76710, 35.68579)
    abolished_end = (139.76711, 35.68580)
    # 地価地点からやや離れた位置（約500m、東京駅の座標相当）に営業中駅を配置
    active_start = (139.7671, 35.6812)
    active_end = (139.7673, 35.6812)

    raw = make_s12_raw_with_coords(
        [
            (
                "廃止駅",
                "999999",
                int(S12Duplicate.RECORDED_ON_THIS_LINE),
                int(S12DataStatus.NO_STATION),
                9999.0,
                abolished_start,
                abolished_end,
            ),
            (
                "東京",
                "003968",
                int(S12Duplicate.RECORDED_ON_THIS_LINE),
                int(S12DataStatus.AVAILABLE),
                462589.0,
                active_start,
                active_end,
            ),
        ]
    )

    extracted = extract_passengers(raw, S12Config(target_year=2024))
    points = to_points(extracted)
    stations = consolidate_by_group(points)
    out = join_nearest_station(land, stations)

    # 廃止駅の方が地価地点に近いが、駅なしとして除外されているため、
    # 営業中の「東京」駅が最寄駅として選ばれる
    assert out[c.STATION_NAME].iloc[0] == "東京"
