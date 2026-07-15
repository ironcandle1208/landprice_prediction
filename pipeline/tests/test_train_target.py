"""目的変数の対数変換テスト。"""

import numpy as np

from landprice.train.target import inverse_log_transform, log_transform


def test_log_transform_roundtrip() -> None:
    """対数変換と逆変換の往復で元の地価へ戻る。"""
    prices = np.array([1.0, 123456.0, 98000000.0], dtype=np.float64)

    restored = inverse_log_transform(log_transform(prices))

    np.testing.assert_allclose(restored, prices, rtol=1e-12)
