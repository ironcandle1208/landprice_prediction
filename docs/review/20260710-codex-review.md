# Codexコードレビュー結果: コミット c537682（前処理パイプライン実装）

- **実施日**: 2026-07-10
- **レビュー担当**: Codex CLI（OpenAI）
- **対象コミット**: c537682「前処理パイプライン実装」
- **対象範囲**: pipeline/ 配下の地価予測用前処理パイプライン（L01地価データ・S12駅乗降客数データの読み込み、最寄り駅探索、特徴量生成、バリデーション、テスト一式）

## 総評

既存の `pytest` 34件、Ruff、mypy はすべて成功。ただし、実データおよび境界ケースで複数のデータ不整合を確認した。

**最優先で直すべき3点**:

1. 対象年度に存在しない駅の除外
2. 必須値の実値検証
3. CRS処理の統一

現状のParquetは正常に生成されるが、一部地点の最寄駅と距離特徴量が正しくない。

---

## 指摘事項

### 1. [高] 対象年度に存在しない駅が最寄駅候補に残る

- [x] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/s12.py:61`

S12の抽出処理では、`NO_STATION` の乗降客数を欠損にするだけで駅レコード自体を残している。そのため、廃止駅・未開業駅が最寄駅として選ばれる。

実データでの確認結果:

- `NO_STATION`: 271レコード
- 全レコードが対象年度に存在しない駅グループ: 34件
- それらが最寄駅として割り当てられた地価地点: 25件
- 例: 留萌、東根室、上野動物園西園、旧グループコード側の金沢

対象年度に存在しないレコードは、駅グループの位置計算からも除外すべき。

```python
# コード体系の変更を欠損扱いで隠さないよう、既知コード以外は拒否する
valid_statuses = {int(value) for value in S12DataStatus}
valid_duplicates = {int(value) for value in S12Duplicate}

unknown_statuses = set(data_status.dropna().astype(int)) - valid_statuses
unknown_duplicates = set(duplicate.dropna().astype(int)) - valid_duplicates
if unknown_statuses or unknown_duplicates:
    raise S12YearColumnsError(
        f"S12に未知のコードがあります: "
        f"データ有無={sorted(unknown_statuses)}, "
        f"重複コード={sorted(unknown_duplicates)}"
    )

# 「データなし」「非公開」は駅自体は存在するので残す。
# 「駅なし」だけを最寄駅探索の候補から除外する。
station_exists = (
    (data_status != S12DataStatus.NO_STATION)
    & (duplicate != S12Duplicate.NO_STATION)
)

result = gpd.GeoDataFrame(
    {
        c.STATION_NAME: station_name,
        c.STATION_GROUP_CODE: group_code,
        c.DATA_STATUS: data_status,
        c.DUPLICATE: duplicate,
        c.PASSENGERS: passengers,
    },
    geometry=gdf.geometry,
    crs=gdf.crs,
)

result = result.loc[station_exists].copy()
if result.empty:
    raise S12YearColumnsError(
        f"{config.target_year}年度に存在する駅がありません"
    )
return result
```

テストには「廃止駅の方が近くても、営業中の駅が選ばれる」統合ケースが必要。

---

### 2. [高] スキーマ検証が型しか見ておらず、必須値の欠損を通す

- [x] 修正済み

**該当箇所**: `pipeline/src/landprice/schema.py:75`

`validate_feature_frame` は dtype の一致しか検査しない。Pydanticモデルは一度もインスタンス化されていないため、`float` や `str` の必須性は実際には検証されない。

再現確認では、以下がすべて欠損でも正常終了した。

- 地価
- 最寄駅距離
- 市区町村コード
- 駅グループコード
- 駅名

また、駅データが0件でも `sjoin_nearest`（`pipeline/src/landprice/preprocess/nearest.py:37`）が全駅属性を欠損にした結果を返し、Parquetまで出力できる。

```python
import numpy as np

def validate_feature_values(df: pd.DataFrame) -> None:
    """特徴量の必須値・有限性・値域を検証する。"""
    required = [
        c.PRICE,
        c.STATION_DISTANCE_M,
        c.CITY_CODE,
        c.STATION_GROUP_CODE,
        c.STATION_NAME,
        c.LON,
        c.LAT,
    ]
    missing_counts = df[required].isna().sum()
    if (missing_counts > 0).any():
        raise FeatureSchemaError(
            f"必須値に欠損があります: "
            f"{missing_counts[missing_counts > 0].to_dict()}"
        )

    if not np.isfinite(df[c.PRICE]).all() or (df[c.PRICE] <= 0).any():
        raise FeatureSchemaError("地価は有限な正数である必要があります")

    if (
        not np.isfinite(df[c.STATION_DISTANCE_M]).all()
        or (df[c.STATION_DISTANCE_M] < 0).any()
    ):
        raise FeatureSchemaError("駅距離は有限な0以上の値である必要があります")

    passengers = df[c.PASSENGERS].dropna()
    if not np.isfinite(passengers).all() or (passengers < 0).any():
        raise FeatureSchemaError("乗降客数は欠損または有限な0以上の値にしてください")

    if not df[c.LON].between(122.0, 154.0).all():
        raise FeatureSchemaError("経度が日本の想定範囲外です")
    if not df[c.LAT].between(20.0, 46.0).all():
        raise FeatureSchemaError("緯度が日本の想定範囲外です")
```

最寄駅結合側でも早期に拒否すべき。

```python
if land.empty:
    raise ValueError("地価データが0件です")
if stations.empty:
    raise ValueError("対象年度に利用可能な駅データが0件です")
if land.geometry.isna().any() or stations.geometry.isna().any():
    raise ValueError("ジオメトリが欠損しています")
```

---

### 3. [高] CRSの扱いが関数ごとに一貫していない

- [x] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/features.py:33`、`pipeline/src/landprice/preprocess/validation.py:25`、`pipeline/src/landprice/preprocess/stations.py:20`

以下の問題がある。

- `build_feature_tables` は、入力が地理座標系なら指定された `geographic_crs` へ変換しない。
- 実際のL01 GeoJSONは `EPSG:4326` だが、設定上の出力CRS `EPSG:6668` は無視される。
- `find_out_of_japan_bounds` はCRSを確認せず `.x/.y` を経緯度として扱う。投影座標系を渡すと正常地点が範囲外になる。
- `to_points` はCRS未設定でも度単位の重心を計算する。また、地理座標系以外なら `metric_crs` を使わず入力CRS上で重心を求める。

常に明示的に変換すること。

```python
def to_points(
    gdf: gpd.GeoDataFrame,
    *,
    metric_crs: str = "EPSG:6691",
) -> gpd.GeoDataFrame:
    """指定したメートル座標系で駅形状の重心を計算する。"""
    if gdf.crs is None:
        raise ValueError("駅データにCRSが設定されていません")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError("駅ジオメトリに欠損または空形状があります")

    projected = gdf.to_crs(metric_crs)
    out = gdf.copy()
    out.geometry = projected.geometry.centroid.to_crs(gdf.crs)
    return out
```

特徴量生成もCRS種別ではなく、CRSの一致で判断すべき。

```python
if joined.crs is None:
    raise ValueError("CRSが設定されていません")

# 地理座標系同士でも測地系が違う可能性があるため、常に指定CRSへ変換する
gdf = joined.to_crs(geographic_crs)
```

座標範囲検証も同様。

```python
if gdf.crs is None:
    raise ValueError("CRS未設定のデータは座標範囲を検証できません")

geographic = gdf.to_crs(geographic_crs)
if not (geographic.geometry.geom_type == "Point").all():
    raise ValueError("座標範囲検証にはPointジオメトリが必要です")

lon = geographic.geometry.x
lat = geographic.geometry.y
```

---

### 4. [中] UTM 54Nを全国一律に使うため西日本・沖縄で距離誤差が大きい

- [ ] 修正済み

**該当箇所**: `pipeline/src/landprice/config.py:76`

`metric_crs` の設定では `EPSG:6691` を全国に適用している。

測地線上の10kmを比較した結果:

| 地域 | UTM 54Nでの距離 | 誤差 |
|---|---:|---:|
| 東京 | 9,997.6m | -0.02% |
| 福岡 | 10,114.8m | +1.15% |
| 石垣島 | 10,363.9m | +3.64% |

「数%を許容する」ことが明示されているが、駅距離をモデル特徴量として使うなら地域ごとに系統的なバイアスが入る。全国処理では、空間インデックスで候補を絞った後、`pyproj.Geod.inv` で測地線距離を確定する方が安全。

```python
from pyproj import Geod

GEOD = Geod(ellps="GRS80")

def geodesic_distance_m(
    land_lon: float,
    land_lat: float,
    station_lon: float,
    station_lat: float,
) -> float:
    """JGD2011楕円体上の2地点間距離をメートルで返す。"""
    _, _, distance_m = GEOD.inv(
        land_lon,
        land_lat,
        station_lon,
        station_lat,
    )
    return float(distance_m)
```

全駅との総当たりは避け、BallTreeや空間インデックスで数件の候補を取得してから測地線距離で最小値を選ぶ構成が適切。

---

### 5. [中] 最寄駅結合が入力行順を変更する

- [ ] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/nearest.py:42`

等距離駅の絞り込みでは、元インデックスでソートしているため入力順が維持されない。

再現例:

```text
入力インデックス:  [20, 10]
出力インデックス:  [10, 20]
```

行数とインデックス値は維持されても、順序依存の後続処理では対応関係を誤る可能性がある。

```python
import numpy as np

land_m = land.to_crs(metric_crs).assign(
    _row_order=np.arange(len(land), dtype="int64")
)

joined = gpd.sjoin_nearest(
    land_m,
    stations_m,
    how="left",
    distance_col=c.STATION_DISTANCE_M,
)

joined = (
    joined.rename_axis("_land_index")
    .reset_index()
    # 等距離時のみグループコードで決定する
    .sort_values(
        ["_row_order", c.STATION_GROUP_CODE],
        kind="stable",
        na_position="last",
    )
    .drop_duplicates("_row_order", keep="first")
    # 最後に元の物理行順へ戻す
    .sort_values("_row_order", kind="stable")
    .set_index("_land_index")
    .drop(columns=["_row_order", "index_right"], errors="ignore")
)
joined.index.name = land.index.name
```

テストは RangeIndex だけでなく、`[20, 10]`、文字列インデックス、名前付きインデックスで確認すべき。

---

### 6. [中] 距離整合検証が異なる駅同士を比較している

- [ ] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/validation.py:42`、`pipeline/src/landprice/preprocess/run.py:75`

`find_distance_inconsistencies` は、L01の駅名と自前探索した駅名が一致するか確認していない。

実データのレポート2,435件中、少なくとも522件は駅名が異なった。例えば「L01: 大通」と「S12: 西4丁目」の距離を比較しており、`直線距離 <= 道路距離` の前提が成立しない。

さらに、`run_pipeline` は許容誤差を指定せず、デフォルトの0mで判定している。

駅名を正規化し、一致した行だけを距離検証対象にすること。駅名不一致は別レポートに分けるべき。

```python
import unicodedata

def normalize_station_name(value: object) -> str | None:
    """駅名を比較用にUnicode正規化する。"""
    if pd.isna(value):
        return None
    return unicodedata.normalize("NFKC", str(value)).strip()

def find_distance_inconsistencies(
    df: pd.DataFrame,
    *,
    tolerance_m: float = 100.0,
) -> pd.DataFrame:
    """同一駅と確認できた行について距離矛盾を検出する。"""
    l01_name = df[c.L01_STATION_NAME].map(normalize_station_name)
    joined_name = df[c.STATION_NAME].map(normalize_station_name)

    comparable = (
        l01_name.notna()
        & joined_name.notna()
        & l01_name.eq(joined_name)
        & df[c.STATION_DISTANCE_M].notna()
        & df[c.L01_ROAD_DISTANCE_M].notna()
    )
    inconsistent = (
        df[c.STATION_DISTANCE_M]
        > df[c.L01_ROAD_DISTANCE_M] + tolerance_m
    )
    return df.loc[comparable & inconsistent].copy()
```

`地下鉄琴似` と `琴似`、全角数字と半角数字などは、別途名称辞書または駅コード対応が必要。

---

### 7. [中] グループコード欠損や未知コードが黙ってデータ欠落へ変換される

- [ ] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/stations.py:43`

`consolidate_by_group` の `groupby` はデフォルトでNAキーを除外する。再現確認では、グループコード欠損の1行が警告なく消えた。

また、S12の未知のデータ有無コード・重複コードは、現在の実装では `valid=False` となって乗降客数の欠損へ変換される。年度更新によるコード体系変更を発見できない。

抽出時にキーを正規化し、欠損は明示的に拒否すること。

```python
group_code = (
    gdf[config.group_code_column]
    .astype("string")
    .str.strip()
    .replace(["", "_"], pd.NA)
)
station_name = (
    gdf[config.station_name_column]
    .astype("string")
    .str.strip()
    .replace(["", "_"], pd.NA)
)

if group_code.isna().any():
    bad_rows = group_code[group_code.isna()].index.tolist()[:10]
    raise S12YearColumnsError(
        f"駅グループコードが欠損しています: 行={bad_rows}"
    )
if station_name.isna().any():
    bad_rows = station_name[station_name.isna()].index.tolist()[:10]
    raise S12YearColumnsError(
        f"駅名が欠損しています: 行={bad_rows}"
    )
```

L01側も必要カラムの直接参照で生の `KeyError` を出すのではなく、不足カラムをまとめて報告すると運用しやすくなる。

---

### 8. [低] 地価地点の安定した識別子が出力から失われる

- [ ] 修正済み

**該当箇所**: `pipeline/src/landprice/preprocess/l01.py:31`

`load_land_points` では、市区町村コードだけを保持し、L01標準地点の複合キーである `L01_001 + L01_002 + L01_003` を落としている。

将来、予測結果を元の標準地点やGeoJSONへ結合する際に、DataFrameの行番号へ依存することになる。前述の行順変更とも相性が悪い。

```python
LAND_POINT_ID = "land_point_id"

# L01ColumnMapへ用途区分・連番の属性コードを追加する
city = gdf[columns.city_code].astype("string").str.strip()
category = gdf[columns.point_category].astype("string").str.strip()
serial = gdf[columns.point_serial].astype("string").str.strip()

data = {
    c.LAND_POINT_ID: city + "-" + category + "-" + serial,
    c.CITY_CODE: city,
    # 以下、既存属性
}
```

特徴量と目的変数も概念上分けると、後続の学習・推論で目的変数を入力特徴量へ混入させにくくなる。

```python
ONLINE_MODEL_COLUMNS = [
    c.STATION_DISTANCE_M,
    c.PASSENGERS,
    c.LON,
    c.LAT,
]

target = full[c.PRICE].rename("target")
online_features = full[ONLINE_MODEL_COLUMNS].copy()
online_training = pd.concat([target, online_features], axis=1)
```

---

## テスト網羅性

現行テストは各関数の正常系を丁寧に押さえているが、パイプライン全体の統合テストがない。最低限、以下を追加すべき。

- `run_pipeline` の一時GeoJSON→Parquet→検証レポート統合テスト
- 対象年度に存在しない駅が候補から除外されるテスト
- 全駅が `NO_STATION` の場合に失敗するテスト
- 空の駅・地価データ、null/空ジオメトリ
- CRS未設定、投影CRS入力、EPSG:4326→6668変換
- 欠損グループコード、未知のS12コード
- 地価・距離・必須文字列の欠損、負数、`inf`
- 非連番インデックスでも入力順を維持するテスト
- L01駅名と探索駅名が異なる場合は距離比較しないテスト
- 東京以外、特に福岡・沖縄での距離精度テスト
- 実データから匿名化・縮小したゴールデンフィクスチャによる属性コード確認
