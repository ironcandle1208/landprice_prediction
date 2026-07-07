"""前処理データ検証のテスト。

docs/plan/test/preprocessing.feature の
「座標が日本の範囲外の地点は検出される」
「自前計算の直線距離がL01付属の道路距離と矛盾しない」に対応。
"""

import pandas as pd
import pytest

from landprice import columns as c
from landprice.preprocess.validation import (
    find_distance_inconsistencies,
    find_out_of_japan_bounds,
)
from tests.conftest import make_land


def test_out_of_japan_bounds_detected() -> None:
    """シナリオ: 座標が日本の範囲外の地点は検出される"""
    land = make_land(
        [
            (139.767, 35.681),  # 東京（正常）
            (200.0, 35.0),  # 経度が範囲外
            (139.0, 60.0),  # 緯度が範囲外
        ]
    )

    # 該当地点が警告として報告される
    with pytest.warns(UserWarning, match="範囲外"):
        bad = find_out_of_japan_bounds(land)

    assert len(bad) == 2
    assert bad["point_id"].tolist() == [1, 2]


def test_no_warning_when_all_points_in_japan() -> None:
    """範囲内のみの場合は警告なしで空の結果を返す（追加テスト）"""
    land = make_land([(139.767, 35.681), (135.5, 34.7)])

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # 警告が出たら失敗させる
        bad = find_out_of_japan_bounds(land)

    assert len(bad) == 0


def test_straight_distance_exceeding_road_distance_reported() -> None:
    """シナリオ: 自前計算の直線距離がL01付属の道路距離と矛盾しない

    直線距離 ≦ 道路距離 が成り立つはずで、矛盾する地点（直線距離 > 道路距離）は
    検証レポートに出力される。
    """
    df = pd.DataFrame(
        {
            "point_id": [0, 1, 2],
            c.STATION_DISTANCE_M: [100.0, 800.0, 300.0],
            c.L01_ROAD_DISTANCE_M: [200.0, 500.0, 300.0],
        }
    )

    report = find_distance_inconsistencies(df)

    # 直線800m > 道路500m の地点のみが矛盾として報告される
    assert report["point_id"].tolist() == [1]


def test_tolerance_absorbs_projection_distortion() -> None:
    """投影座標系の距離歪みによる軽微な逆転は許容誤差で吸収できる（追加テスト）"""
    df = pd.DataFrame(
        {
            "point_id": [0],
            c.STATION_DISTANCE_M: [510.0],  # 歪みで道路距離をわずかに超過
            c.L01_ROAD_DISTANCE_M: [500.0],
        }
    )

    assert len(find_distance_inconsistencies(df, tolerance_m=50.0)) == 0
    assert len(find_distance_inconsistencies(df, tolerance_m=0.0)) == 1
