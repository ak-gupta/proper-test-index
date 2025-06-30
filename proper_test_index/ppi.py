"""Proper player index."""

import polars as pl
from polars._typing import FrameType


def calc_ppi(score: pl.Expr, wave_average: pl.Expr, course_factor: pl.Expr) -> pl.Expr:
    """Calculate a weighted average of score differential.

    Used in aggregation functions.

    Parameters
    ----------
    score : pl.Expr
        An expression that represents the player's round score.
    wave_average : pl.Expr
        An expression that represents the scoring average for a given wave (morning or
        afternoon).
    course_factor : pl.Expr
        An expression that represents the course factor.

    Returns
    -------
    pl.Expr
        An expression that calculates the proper player index.
    """
    return ((wave_average - score) * course_factor).sum() / (course_factor.sum())


def gen_rolling_ppi(
    scoring: FrameType, course_factor: FrameType, period: int = 25
) -> FrameType:
    """Pipe-compatible function for calculating a rolling proper player index.

    Parameters
    ----------
    scoring : dataframe-like
        A polars dataframe/lazyframe with round-by-round scoring data. The dataframe output
        from :py:meth:`proper_test_index.collect.collect_raw_event_data`.
    course_factor : dataframe-like
        A polars dataframe/lazyframe with the course factor and the course number. The output
        from :py:meth:`proper_player_index.pti.calc_course_factor`.
    period : int, optional (default 25)
        The number of rounds to consider in the rolling PTI.

    Returns
    -------
    dataframe-like
        The round-level dataset with a 25-round rolling average proper player index.
    """
    return (
        scoring.drop_nulls("score")  # ZURICH
        .join(course_factor, on="course_num", how="left")
        .with_columns(
            wave=(
                pl.when(pl.col("teetime").dt.hour() < 12)
                .then(pl.lit("morning"))
                .otherwise(pl.lit("afternoon"))
            )
        )
        .with_columns(
            wave_average=pl.col("score")
            .mean()
            .over(["event_id", "year", "round", "wave"])
        )
        .sort("dg_id", "teetime", descending=False)
        .with_row_index()
        .rolling("index", period=f"{period}i", group_by=["dg_id", "player_name"])
        .agg(
            [
                calc_ppi(
                    pl.col("score"),
                    pl.col("wave_average"),
                    pl.col("course_factor_star"),
                ).alias("ppi"),
                pl.col("teetime").last(),
                pl.col("teetime").first().alias("first_tee_time_in_group"),
                pl.len().alias("rounds"),
                pl.mean("sg_total"),
                pl.col("score").last(),
                pl.col("event_name").last(),
                pl.col("wave_average").last(),
                pl.col("course_factor_star").last(),
            ]
        )
        .filter(pl.col("rounds") == period)
        .select(
            [
                "dg_id",
                "player_name",
                "ppi",
                "teetime",
                "first_tee_time_in_group",
                "sg_total",
                "score",
                "event_name",
                "wave_average",
                "course_factor_star",
            ]
        )
        .with_columns(
            category=(
                pl.when(pl.col("sg_total") >= 0, pl.col("ppi") > pl.col("sg_total"))
                .then(pl.lit("Proper Player"))
                .when(pl.col("sg_total") >= 0, pl.col("ppi") <= pl.col("sg_total"))
                .then(pl.lit("Imposter"))
                .when(pl.col("sg_total") < 0, pl.col("ppi") > pl.col("sg_total"))
                .then(pl.lit("Gamer"))
                .otherwise(pl.lit("Mule"))
            ),
            ppi_sg_diff=pl.col("ppi") - pl.col("sg_total"),
        )
        .sort("dg_id", "player_name", "teetime", descending=True)
    )
