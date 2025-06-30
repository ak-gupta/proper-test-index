"""Basic data collection script using proper-test-index."""

import json
import logging
from pathlib import Path

import polars as pl
from attrs import asdict
from dotenv import load_dotenv
from slugify import slugify

from proper_test_index.collect import collect_raw_event_data, retrieve_event_list
from proper_test_index.schemas import ScoreObject, serializer, to_schema

LOG = logging.getLogger(__name__)

CURR_DIR = Path(__file__).resolve().parent
DATA_DIR = CURR_DIR / "data"


# def retrieve_course_info(events: list[tuple[int, int]]) -> list[CourseInfo]:
#     """Retrieve course information.

#     Retrieves longitude and latitude for weather data later.
#     """
#     # TODO: this only gets us the current season
#     response_ = SESSION.get(
#         f"{BASE_URL}/get-schedule/tour",
#         params={"tour": "pga", "file_format": "json", "key": os.getenv("API_TOKEN")},
#     )
#     response_.raise_for_status()
#     out: list[CourseInfo] = []
#     event_ids = [event_id for _, event_id in events]
#     for course in response_.json()["schedule"]:
#         if course["event_id"] in event_ids:
#             out += [
#                 CourseInfo(
#                     course_name=course["course"],
#                     course_num=int(course["course_key"]),
#                     latitude=course["latitude"],
#                     longitude=course["longitude"],
#                     location=course["location"],
#                 )
#             ]

#     return out


# def retrieve_round_weather_data(course: CourseInfo, date: datetime) -> list[dict]:
#     """Get the weather data for a given day on a given course.

#     Parameters
#     ----------
#     course : CourseInfo
#         The course information, specifically the latitude and longitude.
#     date : datetime
#         The day of interest.

#     Returns
#     -------
#     list[dict]
#         A list of observations, with the time, temperature, wind direction, wind velocity, etc.
#     """
#     # First, get the stations in the area
#     # e.g. https://api.weather.gov/points/{course["latitude"]},{course["longitude"]}
#     # this gives us obj["properties"]["observationStations"]
#     # Then, get the relevant stations
#     # e.g. obj["properties"]["observationStations"]?limit=1
#     # this gives us obj2["features"][0]["properties"]["stationIdentifier"]
#     # Then, get observations for the entire day
#     # e.g. https://api.weather.gov/stations/{obj2["features"][0]["properties"]["stationIdentifier"]}/observations
#     # with start and end dates in the format YYYY-MM-DDTHH:MM:SSZ


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    # Load the dotenv file
    load_dotenv(CURR_DIR / ".env")

    DATA_DIR.mkdir(exist_ok=True)
    if not (DATA_DIR / "all-events.json").exists():
        events = retrieve_event_list()
        with open(DATA_DIR / "all-events.json", "w") as outfile:
            json.dump(events, outfile, indent=4)

    for evt in retrieve_event_list():
        folder = DATA_DIR / str(evt["calendar_year"])
        folder.mkdir(exist_ok=True)
        fpath = folder / f"{slugify(evt['event_name'])}-scoring-data.parquet"
        if fpath.exists():
            LOG.info(
                "%i %s data already exists...", evt["calendar_year"], evt["event_name"]
            )
            continue
        score_raw_ = collect_raw_event_data(evt)
        score_data = pl.DataFrame(
            [asdict(obj, value_serializer=serializer) for obj in score_raw_],
            schema=to_schema(ScoreObject),
        )
        score_data.write_parquet(fpath, use_pyarrow=True)
