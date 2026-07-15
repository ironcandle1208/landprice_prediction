"""目的変数の対数変換。"""

import numpy as np
from numpy.typing import ArrayLike, NDArray


def log_transform(values: ArrayLike) -> NDArray[np.float64]:
    """有限な正の実額値を自然対数スケールへ変換する。"""
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all() or (array <= 0).any():
        raise ValueError("対数変換の入力は有限な正数である必要があります")
    return np.log(array)


def inverse_log_transform(values: ArrayLike) -> NDArray[np.float64]:
    """自然対数スケールの値を実額スケールへ逆変換する。"""
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("逆対数変換の入力は有限値である必要があります")
    restored = np.exp(array)
    if not np.isfinite(restored).all():
        raise ValueError("逆対数変換の結果が有限値の範囲を超えました")
    return restored
