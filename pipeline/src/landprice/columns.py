"""前処理パイプラインで用いる論理カラム名の定義。

国土数値情報の属性コード（S12_058・L01_006等）は年度により構成が変わるため、
読み込み直後に本モジュールの論理名へ変換し、以降の処理・テストは論理名のみを参照する。
schema.py のPydanticモデルのフィールド名とも一致させること。
"""

# S12（駅別乗降客数）由来
STATION_NAME = "station_name"  # 駅名（表示専用。識別キーには使わない）
STATION_GROUP_CODE = "station_group_code"  # グループコード（駅グループの識別キー）
DATA_STATUS = "data_status"  # データ有無コード
DUPLICATE = "duplicate"  # 年度別重複コード（二重計上防止フラグ）
PASSENGERS = "passengers"  # 乗降客数（人/日）

# 最寄駅結合で付与
STATION_DISTANCE_M = "station_distance_m"  # 最寄駅までの直線距離（メートル）

# L01（地価公示）由来
PRICE = "price_yen_per_m2"  # 地価（円/m²）
USE_DISTRICT = "use_district"  # 用途地域
FLOOR_AREA_RATIO = "floor_area_ratio"  # 容積率（上限）
CITY_CODE = "city_code"  # 市区町村コード
L01_STATION_NAME = "l01_station_name"  # L01付属の最寄駅名（検証用）
L01_ROAD_DISTANCE_M = "l01_station_road_distance_m"  # L01付属の道路距離（検証用）

# 特徴量テーブルの座標
LON = "lon"
LAT = "lat"
