"""Test PTI calculations."""

import polars as pl
from polars.testing import assert_frame_equal

from proper_test_index.pti import calc_course_factor, calc_pti


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


def test_calc_course_factor():
    """Test calculating course factor."""
    pti = pl.DataFrame(
        {
            "year": [2021, 2021, 2022, 2022],
            "event_id": [1, 2, 1, 2],
            "event_name": "fake",
            "course_name": "fake",
            "course_num": [1, 2, 1, 2],
            "over_80": [1, 0, 2, 3],
            "sub_70": [1, 3, 2, 4],
            "total_rounds": [4, 6, 10, 8],
            "scoring_average": [74.75, 66.25, 72.0, 68.0],
            "pti": [1.0, 0.0, 1.0, 0.75],
            "major_championship": False,
        }
    )
    out = calc_course_factor(pti)

    expected = pl.DataFrame(
        {
            "course_num": [1, 2],
            "course_name": "fake",
            "total_over_80": [3, 3],
            "total_sub_70": [3, 7],
            "total_rounds": [14, 14],
            "scoring_average": [1019.0 / 14.0, 67.25],
            "other_over_80": [3, 3],
            "other_sub_70": [7, 3],
            "course_factor": [100 * (7 / 3), 100 * (3 / 7)],
        }
    ).with_columns(course_factor_star=(pl.lit(1.0) + pl.col("course_factor")).log10())

    assert_frame_equal(out, expected)
