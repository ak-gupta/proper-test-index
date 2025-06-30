"""Simple aggregation code using proper-test-index."""

import logging
from pathlib import Path

import polars as pl

from proper_test_index.ppi import gen_rolling_ppi
from proper_test_index.pti import calc_course_factor, calc_pti
from proper_test_index.schemas import ScoreObject, to_schema

LOG = logging.getLogger(__name__)

CURR_DIR = Path(__file__).resolve().parent
DATA_DIR = CURR_DIR / "data"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    scoring_data = pl.scan_parquet(
        list(DATA_DIR.glob("**/*-scoring-data.parquet")), schema=to_schema(ScoreObject)
    )
    pti = calc_pti(scoring_data)
    pti.write_csv(CURR_DIR / "pti.csv")

    course_factor = calc_course_factor(pti)
    course_factor.write_csv(CURR_DIR / "course_factor.csv")

    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor)
    rolling_ppi.write_parquet(DATA_DIR / "ppi-rolling-25.parquet", use_pyarrow=True)
    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor, 50)
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling-50.parquet", use_pyarrow=True)
    rolling_ppi = gen_rolling_ppi(scoring_data, course_factor, 100)
    rolling_ppi.write_csv(DATA_DIR / "ppi-rolling-100.parquet", use_pyarrow=True)
