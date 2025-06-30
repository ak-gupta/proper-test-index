"""Clean up the larger parquet files."""

from pathlib import Path

import polars as pl

CURR_DIR = Path(__file__).resolve().parent

DATA_DIR = CURR_DIR / ".." / ".." / "data"

if __name__ == "__main__":
    ppi_curr = (
        pl.scan_parquet(DATA_DIR / "ppi-rolling-50.parquet")
        .sort("dg_id", "teetime", descending=False)
        .group_by("dg_id")
        .last()
        .filter(
            pl.col("teetime").dt.year() == 2025,
            (pl.col("teetime") - pl.col("first_tee_time_in_group")).dt.total_days()
            <= 730,
        )
    )
    ppi_curr.collect().write_csv(CURR_DIR / "ppi-curr.csv")

    ppi_jt = (
        pl.scan_parquet(DATA_DIR / "ppi-rolling-50.parquet")
        .filter(pl.col("dg_id") == 14139)
        .sort("teetime", descending=False)
        .with_columns(
            weighted_score=(pl.col("wave_average") - pl.col("score"))
            * pl.col("course_factor_star")
        )
    )
    ppi_jt.collect().write_csv(CURR_DIR / "ppi-jt.csv")
