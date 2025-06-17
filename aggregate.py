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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    frames: list[pl.DataFrame] = []
    for file in DATA_DIR.glob("*-scoring-data.json"):
        LOG.info("Reading in '%s'", str(file))
        frames.append(
            pl.read_json(
                file,
                schema={
                    "year": pl.Int64,
                    "dg_id": pl.Int64,
                    "player_name": pl.String,
                    "round": pl.Int32,
                    "course_name": pl.String,
                    "course_num": pl.Int32,
                    "course_par": pl.Int32,
                    "score": pl.Int32,
                    "teetime": pl.String
                }
            )
        )

    res = (
        pl.concat(frames).lazy()
        .group_by("year", "course_name")
        .agg(
            [
                (pl.col("score") >= 80).sum().alias("over_80"),
                (pl.col("score") < 70).sum().alias("sub_70")
            ]
        )
        .with_columns((pl.col("over_80") / pl.col("sub_70")).alias("pti"))
        .sort("pti", descending=True)
        .collect()
    )
    res.write_csv("pti.csv")
