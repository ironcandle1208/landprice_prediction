"""LightGBMモデルの交差検証・評価・全データ再学習。"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold

from landprice import columns as c
from landprice.config import TrainConfig
from landprice.train.target import inverse_log_transform, log_transform


@dataclass
class ModelTrainingResult:
    """1系統のモデル学習結果。"""

    booster: lgb.Booster
    oof_log_predictions: NDArray[np.float64]
    oof_actual_predictions: NDArray[np.float64]
    metrics: dict[str, object]


def create_cv_splits(
    n_samples: int, *, n_splits: int, seed: int
) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
    """再現可能なK-foldの学習・検証位置インデックスを作成する。"""
    if n_samples < n_splits:
        raise ValueError(
            f"サンプル数（{n_samples}）は分割数（{n_splits}）以上である必要があります"
        )
    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    positions = np.arange(n_samples, dtype=np.int64)
    return [
        (train.astype(np.int64), test.astype(np.int64))
        for train, test in splitter.split(positions)
    ]


def _prepare_features(
    frame: pd.DataFrame,
    feature_names: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    """設定された特徴量を抽出し、カテゴリカル列をLightGBM向けに変換する。"""
    missing = [name for name in feature_names if name not in frame.columns]
    if missing:
        raise ValueError(f"学習に必要な特徴量カラムがありません: {missing}")

    features = frame[feature_names].copy()
    for name in categorical_features:
        # 全行で一度カテゴリ化し、foldごとにカテゴリコードが変わらないようにする。
        features[name] = features[name].astype("category")
    return features


def _lightgbm_params(config: TrainConfig) -> dict[str, str | int | float | bool]:
    """乱数シードを一か所から固定したLightGBMパラメータを作成する。"""
    params = dict(config.lightgbm_params)
    params.update(
        {
            "seed": config.seed,
            "feature_fraction_seed": config.seed,
            "bagging_seed": config.seed,
            "data_random_seed": config.seed,
        }
    )
    return params


def evaluate_predictions(
    actual_log: NDArray[np.float64], predicted_log: NDArray[np.float64]
) -> dict[str, object]:
    """対数・実額の両スケールでRMSEと決定係数を計算する。"""
    actual = inverse_log_transform(actual_log)
    predicted = inverse_log_transform(predicted_log)
    return {
        "log_scale": {
            "rmse": float(np.sqrt(mean_squared_error(actual_log, predicted_log))),
            "r2": float(r2_score(actual_log, predicted_log)),
        },
        "actual_scale": {
            "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted)),
        },
    }


def train_model(
    frame: pd.DataFrame,
    *,
    feature_names: list[str],
    categorical_features: list[str],
    config: TrainConfig,
) -> ModelTrainingResult:
    """OOF評価を行い、最後に全データでLightGBMモデルを再学習する。"""
    features = _prepare_features(frame, feature_names, categorical_features)
    actual_log = log_transform(frame[c.PRICE].to_numpy(dtype=np.float64))
    oof_log = np.full(len(frame), np.nan, dtype=np.float64)
    splits = create_cv_splits(len(frame), n_splits=config.n_splits, seed=config.seed)
    params = _lightgbm_params(config)

    for train_positions, validation_positions in splits:
        train_set = lgb.Dataset(
            features.iloc[train_positions],
            label=actual_log[train_positions],
            categorical_feature=categorical_features,
        )
        fold_model = lgb.train(
            params,
            train_set,
            num_boost_round=config.num_boost_round,
        )
        predictions = fold_model.predict(features.iloc[validation_positions])
        oof_log[validation_positions] = np.asarray(predictions, dtype=np.float64)

    # 未代入があればOOF評価が成立しないため、保存前に明示的に停止する。
    if not np.isfinite(oof_log).all():
        raise RuntimeError("OOF予測に未計算または非有限の値があります")

    full_train_set = lgb.Dataset(
        features,
        label=actual_log,
        categorical_feature=categorical_features,
    )
    final_model = lgb.train(
        params,
        full_train_set,
        num_boost_round=config.num_boost_round,
    )
    metrics = evaluate_predictions(actual_log, oof_log)
    metrics["n_samples"] = len(frame)
    metrics["n_splits"] = config.n_splits

    return ModelTrainingResult(
        booster=final_model,
        oof_log_predictions=oof_log,
        oof_actual_predictions=inverse_log_transform(oof_log),
        metrics=metrics,
    )
