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
                    "sg_app": pl.Float64,
                    "sg_arg": pl.Float64,
                    "sg_ott": pl.Float64,
                    "sg_putt": pl.Float64,
                    "sg_t2g": pl.Float64,
                    "sg_total": pl.Float64,
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
            total_rounds=pl.col("total_rounds").sum(),
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


def gen_rolling_ppi(scoring_data: pl.DataFrame, course_factor: pl.DataFrame, period: int = 25) -> pl.DataFrame:
    """Generate a rolling proper player index."""
    return (
        scoring_data.lazy()
        .drop_nulls("score")  # ZURICH
        .join(course_factor.lazy(), on="course_num", how="left")
        .with_columns(
            wave=(
                pl.when(pl.col("teetime").dt.hour() < 12)
                .then(pl.lit("morning"))
                .otherwise(pl.lit("afternoon"))
            )
        )
        .with_columns(
            day_average=pl.col("score").mean().over(["event_id", "year", "round", "wave"])
        )
        .sort("dg_id", "teetime", descending=False)
        .with_row_index()
        .rolling("index", period=f"{period}i", group_by=["dg_id", "player_name"]).agg(
            [
                ppi(
                    pl.col("score"),
                    pl.col("day_average"),
                    (pl.lit(1.0) + pl.col("course_factor")).log10()
                ).alias("ppi"),
                pl.col("teetime").last(),
                pl.col("teetime").first().alias("first_tee_time_in_group"),
                pl.len().alias("rounds"),
                pl.mean("sg_total"),
                pl.col("score").last(),
                pl.col("event_name").last(),
                pl.col("day_average").last().alias("wave_average"),
                (pl.lit(1.0) + pl.col("course_factor").last()).log10().alias("log_course_factor"),
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
                "log_course_factor"
            ]
        )
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
                pl.mean("sg_app"),
                pl.mean("sg_arg"),
                pl.mean("sg_ott"),
                pl.mean("sg_putt"),
                pl.mean("sg_t2g"),
                pl.mean("sg_total"),
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
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling-25.csv", datetime_format="%Y-%m-%dT%H:%M:%S%.3fZ")
    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor, 50)
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling-50.csv", datetime_format="%Y-%m-%dT%H:%M:%S%.3fZ")
    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor, 100)
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling-100.csv", datetime_format="%Y-%m-%dT%H:%M:%S%.3fZ")

    static_ppi = gen_static_ppi(scoring_data, course_factor)
    static_ppi.write_csv(DATA_DIR / "ppi-static.csv")
