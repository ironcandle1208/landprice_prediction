"""最寄駅結合（sjoin_nearest）のテスト。

docs/plan/test/preprocessing.feature「ルール: 最寄駅の結合（sjoin_nearest）」に対応。
"""

import geopandas as gpd
import pandas as pd
import pytest

from landprice import columns as c
from landprice.preprocess.nearest import join_nearest_station
from tests.helpers import make_land, make_stations

# 東京駅・新橋駅のおおよその座標（経度, 緯度）
TOKYO = (139.7671, 35.6812)
SHIMBASHI = (139.7587, 35.6660)


def test_known_pair_gets_expected_nearest_station() -> None:
    """シナリオ: 既知の座標ペアで期待する最寄駅が付与される"""
    stations = make_stations(
        [
            ("003968", "東京", 462589.0, *TOKYO),
            ("003976", "新橋", 155343.0, *SHIMBASHI),
        ]
    )
    # 東京駅から北へ約500m（緯度 +0.0045度）の地価地点
    land = make_land([(139.7671, 35.6857)])

    out = join_nearest_station(land, stations)

    assert out[c.STATION_NAME].iloc[0] == "東京"


def test_distance_is_in_meters() -> None:
    """シナリオ: 駅距離がメートル単位で計算される"""
    stations = make_stations([("003968", "東京", 462589.0, *TOKYO)])
    land = make_land([(139.7671, 35.6857)])  # 東京駅から約500m

    out = join_nearest_station(land, stations)

    distance = out[c.STATION_DISTANCE_M].iloc[0]
    # 度単位（1未満の極小値）ではなく、メートル単位で約500m
    assert 450.0 < distance < 550.0


def test_all_land_points_get_nearest_station() -> None:
    """シナリオ: すべての地価地点に最寄駅が付与される"""
    stations = make_stations(
        [
            ("003968", "東京", 462589.0, *TOKYO),
            ("003976", "新橋", 155343.0, *SHIMBASHI),
        ]
    )
    land = make_land([(139.5 + 0.005 * i, 35.5 + 0.003 * i) for i in range(100)])

    out = join_nearest_station(land, stations)

    assert out[c.STATION_GROUP_CODE].notna().all()
    assert out[c.STATION_DISTANCE_M].notna().all()


def test_join_preserves_row_count() -> None:
    """シナリオ: 結合で行数が増減しない"""
    stations = make_stations(
        [
            ("003968", "東京", 462589.0, *TOKYO),
            ("003976", "新橋", 155343.0, *SHIMBASHI),
        ]
    )
    land = make_land([(139.5 + 0.005 * i, 35.5 + 0.003 * i) for i in range(100)])

    out = join_nearest_station(land, stations)

    assert len(out) == 100


def test_equidistant_stations_produce_single_reproducible_result() -> None:
    """シナリオ: 等距離に複数の駅がある場合も1駅のみ選ばれ結果が再現する"""
    # 完全に同一座標の駅2つ（地価地点から完全に等距離）
    stations = make_stations(
        [
            ("000200", "駅B", 2000.0, 139.760, 35.680),
            ("000100", "駅A", 1000.0, 139.760, 35.680),
        ]
    )
    land = make_land([(139.765, 35.683)])

    out1 = join_nearest_station(land, stations)
    out2 = join_nearest_station(land, stations)

    # いずれの実行でも1駅のみ付与され、結果が一致する（重複コード順で先頭）
    assert len(out1) == 1
    assert len(out2) == 1
    assert out1[c.STATION_GROUP_CODE].iloc[0] == "000100"
    pd.testing.assert_frame_equal(pd.DataFrame(out1), pd.DataFrame(out2))


def test_remote_island_point_gets_nearest_station() -> None:
    """シナリオ: 離島の地価地点にも最寄駅が付与される"""
    stations = make_stations([("003968", "東京", 462589.0, *TOKYO)])
    # 小笠原・父島付近（最寄駅まで50km以上）
    land = make_land([(142.195, 27.094)])

    out = join_nearest_station(land, stations)

    assert out[c.STATION_NAME].iloc[0] == "東京"
    assert out[c.STATION_DISTANCE_M].iloc[0] > 50_000.0


def test_empty_stations_are_rejected() -> None:
    """シナリオ: 駅データが0件の場合は結合前に拒否する"""
    land = make_land([TOKYO])
    stations = make_stations([])

    with pytest.raises(ValueError, match="対象年度に利用可能な駅データが0件"):
        join_nearest_station(land, stations)


def test_empty_land_is_rejected() -> None:
    """シナリオ: 地価データが0件の場合は結合前に拒否する"""
    land = make_land([])
    stations = make_stations([("003968", "東京", 462589.0, *TOKYO)])

    with pytest.raises(ValueError, match="地価データが0件"):
        join_nearest_station(land, stations)


@pytest.mark.parametrize("missing_geometry", ["land", "stations"])
def test_missing_geometry_is_rejected(missing_geometry: str) -> None:
    """シナリオ: 地価または駅のジオメトリが欠損している場合は拒否する"""
    land = make_land([TOKYO])
    stations = make_stations([("003968", "東京", 462589.0, *TOKYO)])
    target: gpd.GeoDataFrame = land if missing_geometry == "land" else stations
    target.loc[target.index[0], "geometry"] = None

    with pytest.raises(ValueError, match="ジオメトリが欠損"):
        join_nearest_station(land, stations)
