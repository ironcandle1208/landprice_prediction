"""L01地価データ読み込みのテスト。

docs/plan/test/preprocessing.feature「ルール: L01地価データの読み込み」に対応。
"""

import geopandas as gpd
from shapely.geometry import Point

from landprice import columns as c
from landprice.config import L01ColumnMap
from landprice.preprocess.l01 import load_land_points
from tests.helpers import CRS

# テスト用の属性コードマッピング（実データの属性コードは年度により異なる）
# 検証用の任意カラム（最寄駅名・道路距離）はこのフィクスチャには含めない
COLMAP = L01ColumnMap(
    price="L01_100",
    use_district="L01_101",
    floor_area_ratio="L01_102",
    city_code="L01_103",
    station_name=None,
    station_road_distance=None,
)


def make_l01_raw(rows: list[tuple[float, str, float, str]]) -> gpd.GeoDataFrame:
    """L01の生データ形式（属性コードのカラム名）を作る。

    rows: (地価, 用途地域, 容積率, 市区町村コード)
    """
    return gpd.GeoDataFrame(
        {
            "L01_100": [r[0] for r in rows],
            "L01_101": [r[1] for r in rows],
            "L01_102": [r[2] for r in rows],
            "L01_103": [r[3] for r in rows],
        },
        geometry=[Point(139.7 + 0.01 * i, 35.68) for i in range(len(rows))],
        crs=CRS,
    )


def test_required_attributes_extracted() -> None:
    """シナリオ: 必須属性が抽出される"""
    raw = make_l01_raw([(1500000.0, "商業地域", 800.0, "13101")])

    out = load_land_points(raw, COLMAP)

    # 地価（円/m²）・用途地域・容積率・市区町村コードのカラムが存在する
    assert out[c.PRICE].iloc[0] == 1500000.0
    assert out[c.USE_DISTRICT].iloc[0] == "商業地域"
    assert out[c.FLOOR_AREA_RATIO].iloc[0] == 800.0
    assert out[c.CITY_CODE].iloc[0] == "13101"


def test_empty_use_district_kept_as_missing() -> None:
    """シナリオ: 用途地域が未設定の地点は欠損として保持される

    実データ（令和8年版）では未設定の欠損表現として '_' が使われる。
    """
    raw = make_l01_raw(
        [
            (100000.0, "", 200.0, "01100"),  # 空文字
            (200000.0, "  ", 200.0, "01100"),  # 空白のみ
            (250000.0, "_", 200.0, "01100"),  # 実データの欠損表現
            (300000.0, "商業地域", 400.0, "13101"),
        ]
    )

    out = load_land_points(raw, COLMAP)

    # 該当地点の用途地域は欠損（NaN）であり、行自体は削除されない
    assert out[c.USE_DISTRICT].isna().tolist() == [True, True, True, False]
    assert len(out) == 4
