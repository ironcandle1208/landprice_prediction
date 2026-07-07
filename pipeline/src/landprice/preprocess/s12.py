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
    """対象年度のカラムがS12データに存在しない場合の例外。

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
      それ以外（データなし・非公開・駅なし・他路線駅に計上済み）は欠損（NaN）にする。
      0埋めすると欠損を誤学習し、他路線分を残すと名寄せ時に二重計上するため
    - データ有で乗降客数が実際に0の駅は0のまま保持する
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
    # 有効な乗降客数のみ残し、それ以外は欠損にする（値が入っていても信用しない）
    valid = (data_status == S12DataStatus.AVAILABLE) & (
        duplicate == S12Duplicate.RECORDED_ON_THIS_LINE
    )
    passengers = passengers.where(valid, np.nan)

    return gpd.GeoDataFrame(
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
