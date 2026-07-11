"""S12（駅別乗降客数）の対象年度カラム抽出。

S12は年度ごとに4カラム（重複コード・データ有無コード・備考・乗降客数）が
横に増える構造のため、対象年度のカラムだけを抽出して論理名に変換する。
駅グループの識別キー（グループコード）は年度に依存しない独立属性（S12_001g）。
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from landprice import columns as c
from landprice.config import S12Config, S12DataStatus, S12Duplicate


class S12YearColumnsError(ValueError):
    """S12データが対象年度・コード体系の前提と一致しない場合の例外（対象年度カラム欠如／未知コード／除外後0件）。

    黙って欠損値で埋めた結果を返さず、明示的に失敗させるための型。
    """


def year_column_codes(config: S12Config) -> dict[str, str]:
    """対象年度の4カラム（重複コード・データ有無・備考・乗降客数）の属性コードを返す。

    属性コードは開始年度（2011年度=S12_006〜S12_009）からのオフセットで計算する。
    例: 2024年度 → S12_058（重複コード）〜S12_061（乗降客数）
    """
    offset = (config.target_year - config.first_year) * 4
    start = config.first_year_start_index + offset
    return {
        c.DUPLICATE: f"S12_{start:03d}",
        c.DATA_STATUS: f"S12_{start + 1:03d}",
        "remarks": f"S12_{start + 2:03d}",
        c.PASSENGERS: f"S12_{start + 3:03d}",
    }


def extract_passengers(gdf: gpd.GeoDataFrame, config: S12Config) -> gpd.GeoDataFrame:
    """対象年度の乗降客数を抽出し、論理カラム名のGeoDataFrameを返す。

    - 対象年度のカラムが存在しない場合は S12YearColumnsError を送出する
    - 乗降客数が有効なのは「データ有」かつ「当該路線駅に記載」のレコードのみ。
      それ以外（データなし・非公開・他路線駅に計上済み）は欠損（NaN）にする。
      0埋めすると欠損を誤学習し、他路線分を残すと名寄せ時に二重計上するため
    - データ有で乗降客数が実際に0の駅は0のまま保持する
    - 「駅なし」（対象年度に駅が存在しない）のレコードは乗降客数を欠損にするだけでなく、
      行ごと除外する。残すと駅グループの重心計算・最寄駅結合に廃止駅・未開業駅が
      混入し、最寄駅として誤って選ばれるため
    - データ有無コード・重複コードに未知の値（コード体系表に定義のない値）が
      含まれる場合は S12YearColumnsError を送出する。年度更新でコード体系が
      変わった場合に黙って欠損・除外扱いにしないため
    - 除外の結果、対象年度に存在する駅が0件になった場合も S12YearColumnsError を送出する
    - 出力には対象年度以外の年度カラムは含まれない
    """
    codes = year_column_codes(config)
    required = [config.station_name_column, config.group_code_column, *codes.values()]
    missing = [col for col in required if col not in gdf.columns]
    if missing:
        raise S12YearColumnsError(
            f"S12に対象年度{config.target_year}のカラムが存在しません: {missing}。"
            "対象年度の設定（S12Config）とデータの年度版が一致しているか確認してください"
        )

    duplicate = pd.to_numeric(gdf[codes[c.DUPLICATE]])
    data_status = pd.to_numeric(gdf[codes[c.DATA_STATUS]])
    passengers = pd.to_numeric(gdf[codes[c.PASSENGERS]]).astype("float64")

    # コード体系の変更を欠損扱いで隠さないよう、既知コード以外は拒否する
    # （コード自体が欠損＝NaNの行は本チェックの対象外とし、駅ありとして扱う）
    valid_statuses = {int(value) for value in S12DataStatus}
    valid_duplicates = {int(value) for value in S12Duplicate}
    unknown_statuses = set(data_status.dropna().astype(int)) - valid_statuses
    unknown_duplicates = set(duplicate.dropna().astype(int)) - valid_duplicates
    if unknown_statuses or unknown_duplicates:
        raise S12YearColumnsError(
            f"S12に未知のコードがあります: "
            f"データ有無={sorted(unknown_statuses)}, 重複コード={sorted(unknown_duplicates)}。"
            "年度更新でコード体系が変わっていないか確認してください"
        )

    # 有効な乗降客数のみ残し、それ以外は欠損にする（値が入っていても信用しない）
    valid = (data_status == S12DataStatus.AVAILABLE) & (
        duplicate == S12Duplicate.RECORDED_ON_THIS_LINE
    )
    passengers = passengers.where(valid, np.nan)

    result = gpd.GeoDataFrame(
        {
            c.STATION_NAME: gdf[config.station_name_column].astype("string"),
            c.STATION_GROUP_CODE: gdf[config.group_code_column].astype("string"),
            c.DATA_STATUS: data_status,
            c.DUPLICATE: duplicate,
            c.PASSENGERS: passengers,
        },
        geometry=gdf.geometry,
        crs=gdf.crs,
    )

    # 「駅なし」（対象年度に駅が存在しない）は駅グループの位置計算からも除外する。
    # 「データなし」「非公開」は駅自体は存在するので残す（乗降客数のみ欠損のまま）
    station_exists = (data_status != S12DataStatus.NO_STATION) & (
        duplicate != S12Duplicate.NO_STATION
    )
    result = result.loc[station_exists].copy()
    if result.empty:
        raise S12YearColumnsError(f"{config.target_year}年度に存在する駅がありません")
    return result
