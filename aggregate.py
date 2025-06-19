# /// script
# dependencies = [
#     "polars",
# ]
# ///

import logging
from pathlib import Path
import polars as pl

LOG = logging.getLogger(__name__)

CURR_DIR = Path(__file__).resolve().parent
DATA_DIR = CURR_DIR / "data"

MAJORS: list[str] = [
    14,  # Masters
    536,  # Masters #2
    33,  # PGA
    26,  # US Open
    100,  # Open
]


def read_scoring_data() -> pl.DataFrame:
    """Read scoring data."""
    frames: list[pl.DataFrame] = []
    for file in DATA_DIR.glob("**/*-scoring-data.json"):
        LOG.info("Reading in '%s'", str(file))
        frames.append(
            pl.read_json(
                file,
                schema={
                    "year": pl.Int64,
                    "event_id": pl.Int32,
                    "event_name": pl.String,
                    "dg_id": pl.Int64,
                    "player_name": pl.String,
                    "round": pl.Int32,
                    "course_name": pl.String,
                    "course_num": pl.Int32,
                    "course_par": pl.Int32,
                    "score": pl.Int32,
                    "teetime": pl.Datetime,
                },
            )
        )

    return pl.concat(frames)


def gen_pti_summary(data: pl.DataFrame) -> pl.DataFrame:
    """Generate PTI summary."""
    return (
        data.lazy()
        .group_by("year", "event_id", "event_name", "course_name", "course_num")
        .agg(
            [
                (pl.col("score") >= 80).sum().alias("over_80"),
                (pl.col("score") < 70).sum().alias("sub_70"),
                pl.len().alias("total_rounds"),
                pl.col("score").mean().alias("scoring_average")
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
        .collect()
    )


def gen_course_factor(pti: pl.DataFrame) -> pl.DataFrame:
    """Generate a 'course factor'."""
    return (
        pti.lazy()
        .group_by("course_num")
        .agg(
            course_name=pl.col("course_name").first(),
            total_over_80=pl.col("over_80").sum(),
            total_sub_70=pl.col("sub_70").sum(),
            scoring_average=(pl.col("scoring_average") * pl.col("total_rounds")).sum() / pl.col("total_rounds").sum()
        )
        .with_columns(
            other_over_80=pl.col("total_over_80").sum() - pl.col("total_over_80"),
            other_sub_70=pl.col("total_sub_70").sum() - pl.col("total_sub_70"),
        )
        .with_columns(
            course_factor=pl.lit(100) * ((pl.col("total_over_80") / pl.col("total_sub_70")) / (pl.col("other_over_80") / pl.col("other_sub_70")))
        )
        .sort("course_factor", descending=True)
        .collect()
    )


def ppi(score: pl.Expr, day_average: pl.Expr, course_factor: pl.Expr) -> pl.Expr:
    """Basic expression of proper player index."""
    return (
        (day_average - score) * course_factor
    ).sum() / (
        course_factor.sum()
    )


def gen_rolling_ppi(scoring_data: pl.DataFrame, course_factor: pl.DataFrame, period: str = "6mo") -> pl.DataFrame:
    """Generate a rolling proper player index."""
    return (
        scoring_data.lazy()
        .drop_nulls("score")  # ZURICH
        .join(course_factor.lazy(), on="course_num", how="left")
        .with_columns(
            day_average=pl.col("score").mean().over(["event_id", "year", "round"])
        )
        .sort("teetime", descending=False)
        .rolling("teetime", period=period, group_by=["dg_id", "player_name"]).agg(
            [
                ppi(
                    pl.col("score"),
                    pl.col("day_average"),
                    pl.col("course_factor")
                ).alias("ppi")
            ]
        )
        .drop_nans("ppi")  # All the leading rounds that don't have enough data
        .sort("dg_id", "player_name", "teetime", descending=True)
        .collect()
    )


def gen_static_ppi(scoring_data: pl.DataFrame, course_factor: pl.DataFrame) -> pl.DataFrame:
    """Generate a static PPI."""
    return (
        scoring_data.lazy()
        .drop_nulls("score")  # ZURICH
        .join(course_factor.lazy(), on="course_num", how="left")
        .with_columns(
            day_average=pl.col("score").mean().over(["event_id", "year", "round"])
        )
        .sort("teetime", descending=False)
        .group_by("dg_id", "player_name").agg(
            [
                ppi(
                    pl.col("score"),
                    pl.col("day_average"),
                    pl.col("course_factor")
                ).alias("ppi"),
                pl.len().alias("rounds")
            ]
        )
        .filter(pl.col("rounds") >= 100)
        .sort("ppi", descending=True)
        .collect()
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    scoring_data = read_scoring_data()
    pti = gen_pti_summary(scoring_data)
    pti.write_csv(CURR_DIR / "pti.csv")

    course_factor = gen_course_factor(pti)
    course_factor.write_csv(CURR_DIR / "course_factor.csv")

    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor)
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling.csv")

    static_ppi = gen_static_ppi(scoring_data, course_factor)
    static_ppi.write_csv(DATA_DIR / "ppi-static.csv")
