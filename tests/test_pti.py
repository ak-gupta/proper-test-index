"""Test PTI calculations."""

import polars as pl
from polars.testing import assert_frame_equal

from proper_test_index.pti import calc_pti


def test_calc_pti():
    """Test calculating the PTI."""
    scoring = pl.DataFrame(
        {
            "year": 2021,
            "event_id": [1, 1, 1, 1, 2, 2, 2, 2],
            "event_name": "fake",
            "course_name": "fake",
            "course_num": [1, 1, 1, 1, 2, 2, 2, 2],
            "score": [78, 76, 80, 65, 65, 65, 65, 70],
        }
    )
    pti = calc_pti(scoring)

    expected = pl.DataFrame(
        {
            "year": 2021,
            "event_id": [1, 2],
            "event_name": "fake",
            "course_name": "fake",
            "course_num": [1, 2],
            "over_80": [1, 0],
            "sub_70": [1, 3],
            "total_rounds": 4,
            "scoring_average": [74.75, 66.25],
            "pti": [1.0, 0.0],
            "major_championship": [False, False],
        }
    )
    assert_frame_equal(pti, expected, check_dtypes=False)
