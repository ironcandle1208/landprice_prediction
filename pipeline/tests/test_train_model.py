"""交差検証の分割ロジックテスト。"""

import numpy as np

from landprice.train.model import create_cv_splits


def test_cv_splits_have_no_leakage_and_cover_all_rows() -> None:
    """各foldの学習・検証が重複せず、全行が検証に一度ずつ現れる。"""
    n_samples = 23
    splits = create_cv_splits(n_samples, n_splits=5, seed=42)
    all_validation_positions: list[int] = []

    for train_positions, validation_positions in splits:
        assert np.intersect1d(train_positions, validation_positions).size == 0
        assert len(train_positions) + len(validation_positions) == n_samples
        all_validation_positions.extend(validation_positions.tolist())

    assert sorted(all_validation_positions) == list(range(n_samples))
    assert len(all_validation_positions) == len(set(all_validation_positions))
