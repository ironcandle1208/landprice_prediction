"""パイプライン設定（Pydantic）。

年度・カラムマッピング等、データの年度更新で変わりうる値をここに集約する。
次年度更新時はコード変更なしで本設定の変更のみで切り替えられるようにする
（実装計画「前処理パイプライン構築」参照）。

コード値・属性コードは2026-07-07にダウンロードした実データ
（S12-25: KsjAppSchema-S12-v3_3.xsd / L01-26: GML要素順との突き合わせ）で確認済み。
年度更新時は対象年度の製品仕様書・コードリストで再確認すること。
"""

from enum import IntEnum

from pydantic import BaseModel


class S12DataStatus(IntEnum):
    """S12のデータ有無コード（CodeofDataExistenceorNonexistence）。"""

    AVAILABLE = 1  # データ有
    MISSING = 2  # データなし
    PRIVATE = 3  # 非公開
    NO_STATION = 4  # 駅なし（当該年度に駅が存在しない）


class S12Duplicate(IntEnum):
    """S12の年度別重複コード（CodeofDuplicate）。

    同一駅を複数路線が共有する場合の二重計上を防ぐためのコード。
    乗降客数が有効なのは「当該路線駅に記載」のレコードのみ。
    """

    RECORDED_ON_THIS_LINE = 1  # 当該路線駅に記載（乗降客数はこのレコードに計上）
    RECORDED_ON_OTHER_LINE = 2  # 他路線駅に記載（乗降客数は別レコードに計上済み）
    NO_STATION = 3  # 駅なし


class S12Config(BaseModel):
    """S12（駅別乗降客数）関連の設定。

    S12は年度ごとに4カラム（重複コード・データ有無コード・備考・乗降客数）が
    横に増える構造のため、属性コードを「開始年度からのオフセット」で計算する。
    例: 2011年度 → S12_006〜009、2024年度 → S12_058〜061
    """

    target_year: int = 2024  # 採用する年度（実装計画で2024年度に確定済み）
    first_year: int = 2011  # 収録開始年度（カラム位置計算の基準）
    first_year_start_index: int = 6  # 開始年度の重複コードの属性番号（S12_006）
    station_name_column: str = "S12_001"  # 駅名（表示専用）
    # 駅グループの識別キー。「同名かつ300m以内」の駅グループに対し、
    # グループ重心に最も近い駅の駅コードを持たせた属性（製品仕様書の「グループコード」。
    # 実装計画では「重複コード」と呼んでいたが、年度別の重複コードとは別物）
    group_code_column: str = "S12_001g"


class L01ColumnMap(BaseModel):
    """L01（地価公示）の属性コード→論理名のマッピング。

    L01の属性は「L01_xxx」形式の連番で年度により構成が変わる。
    デフォルト値は令和8年版（L01-26）でGML要素名と突き合わせて確認済み。
    """

    price: str = "L01_008"  # 地価（円/m²）: postedLandPrice
    use_district: str = "L01_051"  # 用途地域: useDistrict
    floor_area_ratio: str = "L01_058"  # 容積率（上限）: floorAreaRatio
    city_code: str = "L01_001"  # 市区町村コード: administrativeAreaCode（当年）
    station_name: str | None = "L01_048"  # 最寄駅名: nameOfNearestStation（検証用）
    station_road_distance: str | None = "L01_050"  # 道路距離(m): distanceFromStation（検証用）


class PipelineConfig(BaseModel):
    """前処理パイプライン全体の設定。"""

    s12: S12Config = S12Config()
    l01_columns: L01ColumnMap = L01ColumnMap()
    # 距離計算用の投影座標系。JGD2011 / UTM zone 54N。
    # 単一CRSのため中央経線（東経141度）から離れる沖縄等では数%の距離歪みがある。
    # 特徴量用途では許容し、L01道路距離との整合検証は許容誤差つきで行う。
    metric_crs: str = "EPSG:6691"
    # 地理座標系（lon/lat出力用）。JGD2011。
    geographic_crs: str = "EPSG:6668"
    # 日本の座標範囲（座標検証用。実装計画のテストシナリオ準拠）
    japan_lon_range: tuple[float, float] = (122.0, 154.0)
    japan_lat_range: tuple[float, float] = (20.0, 46.0)
