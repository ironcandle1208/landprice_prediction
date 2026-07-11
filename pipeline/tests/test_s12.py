"""S12の対象年度カラム抽出のテスト。

docs/plan/test/preprocessing.feature「ルール: S12の対象年度カラム抽出」に対応。
コード値はS12-25のスキーマ定義（KsjAppSchema-S12-v3_3.xsd）で確認済み:
- データ有無コード: 1=データ有, 2=データなし, 3=非公開, 4=駅なし
- 重複コード: 1=当該路線駅に記載, 2=他路線駅に記載, 3=駅なし
「駅なし」（データ有無コード=4 / 重複コード=3）のレコードは行ごと除外される。
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from landprice import columns as c
from landprice.config import S12Config, S12DataStatus, S12Duplicate
from landprice.preprocess.s12 import S12YearColumnsError, extract_passengers
from tests.conftest import CRS


def make_s12_raw(rows: list[tuple[str, str, int, int, float]]) -> gpd.GeoDataFrame:
    """S12の生データ形式（2022〜2024年度が横に並ぶ）を作る。

    rows: (駅名, グループコード, 重複コード2024, データ有無コード2024, 乗降客数2024)
    2022・2023年度のカラムにはダミー値（111・222）を入れ、
    対象年度以外が抽出されないことを検証できるようにする。
    """
    n = len(rows)
    data: dict[str, list[object]] = {
        "S12_001": [r[0] for r in rows],  # 駅名
        "S12_001c": [r[1] for r in rows],  # 駅コード
        "S12_001g": [r[1] for r in rows],  # グループコード
        # 2022年度（S12_050〜053）
        "S12_050": [1] * n,
        "S12_051": [1] * n,
        "S12_052": [""] * n,
        "S12_053": [111.0] * n,
        # 2023年度（S12_054〜057）
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
    geometry = [LineString([(139.70, 35.68), (139.701, 35.681)])] * n
    return gpd.GeoDataFrame(data, geometry=geometry, crs=CRS)


def test_extracts_only_target_year_columns() -> None:
    """シナリオ: 対象年度の乗降客数カラムだけが抽出される"""
    raw = make_s12_raw([("東京", "003968", 1, 1, 462589.0), ("新橋", "003976", 1, 1, 155343.0)])

    out = extract_passengers(raw, S12Config(target_year=2024))

    # 2024年度の値が抽出される
    assert out[c.PASSENGERS].tolist() == [462589.0, 155343.0]
    # 他年度のカラム（値111・222）は出力に含まれない
    assert set(out.columns) == {
        c.STATION_NAME,
        c.STATION_GROUP_CODE,
        c.DATA_STATUS,
        c.DUPLICATE,
        c.PASSENGERS,
        "geometry",
    }


def test_missing_year_columns_raise_explicit_error() -> None:
    """シナリオ: 指定年度のカラムが存在しない場合は明示的なエラーになる"""
    raw = make_s12_raw([("東京", "003968", 1, 1, 462589.0)])

    # 2030年度のカラムは存在しないため、黙って欠損で埋めずに例外を送出する
    with pytest.raises(S12YearColumnsError, match="2030"):
        extract_passengers(raw, S12Config(target_year=2030))


@pytest.mark.parametrize(
    ("status", "raw_value", "expected_nan"),
    [
        (S12DataStatus.AVAILABLE, 5000.0, False),  # データ有 → 元の値のまま
        (S12DataStatus.MISSING, 9999.0, True),  # データなし → 欠損（NaN）
        (S12DataStatus.PRIVATE, 9999.0, True),  # 非公開 → 欠損（NaN）
        # NO_STATIONは行ごと除外されるため、ここでは検証せず
        # test_no_station_records_are_excluded で別途検証する
    ],
)
def test_data_status_controls_passenger_value(
    status: S12DataStatus, raw_value: float, expected_nan: bool
) -> None:
    """シナリオテンプレート: データ有無コードに応じて乗降客数の値を決定する"""
    raw = make_s12_raw([("駅A", "000001", 1, int(status), raw_value)])

    out = extract_passengers(raw, S12Config(target_year=2024))

    if expected_nan:
        assert pd.isna(out[c.PASSENGERS].iloc[0])
    else:
        assert out[c.PASSENGERS].iloc[0] == raw_value


@pytest.mark.parametrize(
    ("duplicate", "expected_nan"),
    [
        (S12Duplicate.RECORDED_ON_THIS_LINE, False),  # 当該路線駅に記載 → 有効
        (S12Duplicate.RECORDED_ON_OTHER_LINE, True),  # 他路線駅に記載 → 欠損（二重計上防止）
        # NO_STATIONは行ごと除外されるため、ここでは検証せず
        # test_duplicate_no_station_records_are_excluded で別途検証する
    ],
)
def test_duplicate_code_controls_passenger_value(
    duplicate: S12Duplicate, expected_nan: bool
) -> None:
    """シナリオテンプレート: 重複コードに応じて乗降客数の有効性を決定する

    「他路線駅に記載」のレコードの値を残すと、駅グループ名寄せの合算時に
    同じ乗降客数を二重計上するため欠損として扱う。
    """
    raw = make_s12_raw([("駅C", "000003", int(duplicate), 1, 7777.0)])

    out = extract_passengers(raw, S12Config(target_year=2024))

    if expected_nan:
        assert pd.isna(out[c.PASSENGERS].iloc[0])
    else:
        assert out[c.PASSENGERS].iloc[0] == 7777.0


def test_zero_passengers_kept_as_zero() -> None:
    """シナリオ: 乗降客数が実際に0の駅は0のまま保持される"""
    raw = make_s12_raw([("駅B", "000002", 1, int(S12DataStatus.AVAILABLE), 0.0)])

    out = extract_passengers(raw, S12Config(target_year=2024))

    # 0は欠損（NaN）に変換されない
    assert out[c.PASSENGERS].iloc[0] == 0.0
    assert not np.isnan(out[c.PASSENGERS].iloc[0])


def test_no_station_records_are_excluded() -> None:
    """シナリオ: 駅なしのレコードは結果から除外される"""
    raw = make_s12_raw(
        [
            ("駅A", "000001", 1, int(S12DataStatus.AVAILABLE), 1000.0),
            ("駅B", "000002", 1, int(S12DataStatus.NO_STATION), 9999.0),
        ]
    )

    out = extract_passengers(raw, S12Config(target_year=2024))

    # 駅なし（駅B）は行ごと除外され、駅Aのみが残る
    assert len(out) == 1
    assert out[c.STATION_NAME].tolist() == ["駅A"]


def test_duplicate_no_station_records_are_excluded() -> None:
    """シナリオ: 重複コードが駅なしのレコードも結果から除外される"""
    raw = make_s12_raw(
        [
            ("駅A", "000001", int(S12Duplicate.RECORDED_ON_THIS_LINE), 1, 1000.0),
            ("駅B", "000002", int(S12Duplicate.NO_STATION), 1, 9999.0),
        ]
    )

    out = extract_passengers(raw, S12Config(target_year=2024))

    # 重複コードが駅なし（駅B）は行ごと除外され、駅Aのみが残る
    assert len(out) == 1
    assert out[c.STATION_NAME].tolist() == ["駅A"]


def test_unknown_data_status_code_raises_error() -> None:
    """シナリオ: 未知のコードはエラーになる（データ有無コード）"""
    # 9はデータ有無コードとして未定義の値
    raw = make_s12_raw([("駅A", "000001", 1, 9, 1000.0)])

    with pytest.raises(S12YearColumnsError, match="未知のコード"):
        extract_passengers(raw, S12Config(target_year=2024))


def test_unknown_duplicate_code_raises_error() -> None:
    """シナリオ: 未知のコードはエラーになる（重複コード）"""
    # 9は重複コードとして未定義の値
    raw = make_s12_raw([("駅A", "000001", 9, 1, 1000.0)])

    with pytest.raises(S12YearColumnsError, match="未知のコード"):
        extract_passengers(raw, S12Config(target_year=2024))


def test_all_rows_no_station_raises_error() -> None:
    """シナリオ: 対象年度に存在する駅が0件の場合はエラーになる"""
    raw = make_s12_raw(
        [
            ("駅A", "000001", 1, int(S12DataStatus.NO_STATION), 9999.0),
            ("駅B", "000002", 1, int(S12DataStatus.NO_STATION), 9999.0),
        ]
    )

    with pytest.raises(S12YearColumnsError, match="存在する駅がありません"):
        extract_passengers(raw, S12Config(target_year=2024))
