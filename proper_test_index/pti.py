"""Proper Test Index."""

import polars as pl
from polars._typing import FrameType

MAJORS: list[str] = [
    14,  # Masters
    536,  # Masters #2
    33,  # PGA
    26,  # US Open
    100,  # Open
]


def calc_pti(scoring: FrameType) -> FrameType:
    """Calculate the proper test index.

    Parameters
    ----------
    scoring : dataframe-like
        A polars dataframe/lazyframe with round-by-round scoring data. The dataframe output
        from :py:meth:`proper_test_index.collect.collect_raw_event_data`.

    Returns
    -------
    dataframe-like
        The polars dataframe/lazyframe with the proper test index.
    """
    return (
        scoring.lazy()
        .group_by("year", "event_id", "event_name", "course_name", "course_num")
        .agg(
            [
                (pl.col("score") >= 80).sum().alias("over_80"),
                (pl.col("score") < 70).sum().alias("sub_70"),
                pl.len().alias("total_rounds"),
                pl.col("score").mean().alias("scoring_average"),
            ]
        )
        .with_columns(
            (pl.col("over_80") / pl.col("sub_70")).round(3).alias("pti"),
            (
                pl.when(pl.col("event_id").is_in(MAJORS)).then(True).otherwise(False)
            ).alias("major_championship"),
        )
        .drop_nans()
        .sort("pti", descending=True)
    )


def calc_course_factor(pti: FrameType) -> FrameType:
    """Calculate the course factor.

    Parameters
    ----------
    pti : dataframe-like
        The output from :py:meth:`proper_test_index.pti.calc_pti`.

    Returns
    -------
    dataframe-like
        The course-level dataset with course factor and log course factor.
    """
    return (
        pti.lazy()
        .group_by("course_num")
        .agg(
            course_name=pl.col("course_name").first(),
            total_over_80=pl.col("over_80").sum(),
            total_sub_70=pl.col("sub_70").sum(),
            total_rounds=pl.col("total_rounds").sum(),
            scoring_average=(pl.col("scoring_average") * pl.col("total_rounds")).sum()
            / pl.col("total_rounds").sum(),
        )
        .with_columns(
            other_over_80=pl.col("total_over_80").sum() - pl.col("total_over_80"),
            other_sub_70=pl.col("total_sub_70").sum() - pl.col("total_sub_70"),
        )
        .with_columns(
            course_factor=pl.lit(100)
            * (
                (pl.col("total_over_80") / pl.col("total_sub_70"))
                / (pl.col("other_over_80") / pl.col("other_sub_70"))
            )
        )
        .with_columns(
            course_factor_star=(pl.lit(1.0) + pl.col("course_factor")).log10()
        )
        .sort("course_factor", descending=True)
    )
