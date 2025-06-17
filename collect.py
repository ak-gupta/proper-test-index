# /// script
# dependencies = [
#     "attrs",
#     "python-dotenv",
#     "python-slugify",
#     "requests",
#     "urllib3",
# ]
# ///

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from attrs import asdict, Attribute, define
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from slugify import slugify
from urllib3.util.retry import Retry

LOG = logging.getLogger(__name__)

CURR_DIR = Path(__file__).resolve().parent
DATA_DIR = CURR_DIR / "data"

SESSION = requests.Session()
RETRIES = Retry(total=10, backoff_factor=2, status_forcelist=[502, 503, 504])
ADAPTER = HTTPAdapter(max_retries=RETRIES)
SESSION.mount("http://", ADAPTER)
SESSION.mount("https://", ADAPTER)

BASE_URL = "https://feeds.datagolf.com"


@define(auto_attribs=True)
class ScoreObject:
    """Scoring object.

    Defines the attributes for raw player/round-level scoring.
    """

    year: int
    event_id: int
    event_name: str
    dg_id: int
    player_name: str
    round: int
    course_name: str
    course_num: int
    course_par: int
    score: int
    teetime: datetime | None = None


@define(auto_attribs=True)
class CourseInfo:
    """Course information.

    Used in conjunction with the NOAA weather service to get approximate weather conditions
    for a given round.
    """

    course_name: str
    course_num: int
    latitude: float
    longitude: float
    location: str


def retrieve_event_list() -> list:
    """Get the list of PGA Tour event IDs.

    Returns
    -------
    list
        The output from the event list API.
    """
    LOG.info("Retrieving list of events...")
    response_ = SESSION.get(
        f"{BASE_URL}/historical-raw-data/event-list",
        params={"file_format": "json", "key": os.getenv("API_TOKEN")},
    )
    response_.raise_for_status()
    out: list = []
    for itm in response_.json():
        if itm["tour"] != "pga":
            continue
        out.append(itm)

    return out


def retrieve_course_info(events: list[tuple[int, int]]) -> list[CourseInfo]:
    """Retrieve course information.

    Retrieves longitude and latitude for weather data later.
    """
    # TODO: this only gets us the current season
    response_ = SESSION.get(
        f"{BASE_URL}/get-schedule/tour",
        params={"tour": "pga", "file_format": "json", "key": os.getenv("API_TOKEN")},
    )
    response_.raise_for_status()
    out: list[CourseInfo] = []
    event_ids = [event_id for _, event_id in events]
    for course in response_.json()["schedule"]:
        if course["event_id"] in event_ids:
            out += [
                CourseInfo(
                    course_name=course["course"],
                    course_num=int(course["course_key"]),
                    latitude=course["latitude"],
                    longitude=course["longitude"],
                    location=course["location"],
                )
            ]

    return out


def collect_raw_event_data(event: dict) -> list[ScoreObject]:
    """Collect raw event data.

    Parameters
    ----------
    event : dict
        The event data from ``retrieve_event_list``.

    Returns
    -------
    list[ScoreObject]
        A list of round-level scores.
    """
    out: list[ScoreObject] = []
    LOG.info("Retrieving scores for the %i %s (%i)", event["calendar_year"], event["event_name"], event["event_id"])
    response_ = SESSION.get(
        f"{BASE_URL}/historical-raw-data/rounds",
        params={
            "tour": "pga",
            "event_id": event["event_id"],
            "year": event["calendar_year"],
            "file_format": "json",
            "key": os.getenv("API_TOKEN"),
        },
    )
    response_.raise_for_status()
    LOG.info("Successfully retrieved %i %s scores", event["calendar_year"], event["event_name"])
    completion_date = datetime.strptime(response_.json()["event_completed"], "%Y-%m-%d")
    for player in response_.json()["scores"]:
        for i in range(1, 5):  # Each round
            if (round_data := player.get(f"round_{i!s}")) is not None:
                obj = ScoreObject(
                    year=event["calendar_year"],
                    event_id=event["event_id"],
                    event_name=event["event_name"],
                    dg_id=player["dg_id"],
                    player_name=player["player_name"],
                    round=i,
                    course_name=round_data["course_name"],
                    course_num=round_data["course_num"],
                    course_par=round_data["course_par"],
                    score=round_data["score"],
                )
                if (teetime := round_data.get("teetime")) is not None:
                    # Make the assumption that round 1 is always on a Thursday
                    # Account for Monday finishes
                    if completion_date.weekday() == 0:
                        round_date = completion_date + timedelta(days=i - 5)
                    elif completion_date.weekday() == 6:
                        round_date = completion_date + timedelta(days=i - 4)
                    elif completion_date.weekday() == 5:
                        # 54-hole tournament
                        round_date = completion_date + timedelta(days=i - 3)
                    else:
                        msg = (
                            f"{event['calendar_year']} {event['event_name']} ({event['event_id']}) "
                            f"didn't finish on Sunday or Monday... it finished on {completion_date.strftime('%A')}"
                        )
                        raise ValueError(msg)

                    assert round_date.weekday() == i + 2, "Datetime math is bad"

                    parsed_teetime = datetime.strptime(teetime, "%I:%M%p")
                    obj.teetime = datetime(
                        round_date.year,
                        round_date.month,
                        round_date.day,
                        parsed_teetime.hour,
                        parsed_teetime.minute,
                        0,
                    )
                out.append(obj)

    return out


def retrieve_round_weather_data(course: CourseInfo, date: datetime) -> list[dict]:
    """Get the weather data for a given day on a given course.

    Parameters
    ----------
    course : CourseInfo
        The course information, specifically the latitude and longitude.
    date : datetime
        The day of interest.

    Returns
    -------
    list[dict]
        A list of observations, with the time, temperature, wind direction, wind velocity, etc.
    """
    # First, get the stations in the area
    # e.g. https://api.weather.gov/points/{course["latitude"]},{course["longitude"]}
    # this gives us obj["properties"]["observationStations"]
    # Then, get the relevant stations
    # e.g. obj["properties"]["observationStations"]?limit=1
    # this gives us obj2["features"][0]["properties"]["stationIdentifier"]
    # Then, get observations for the entire day
    # e.g. https://api.weather.gov/stations/{obj2["features"][0]["properties"]["stationIdentifier"]}/observations
    # with start and end dates in the format YYYY-MM-DDTHH:MM:SSZ


def serializer(inst: type, field: Attribute, value: Any) -> Any:
    """Datetime converter for :py:meth:`attrs.asdict`."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


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
        folder = (DATA_DIR / str(evt["calendar_year"]))
        folder.mkdir(exist_ok=True)
        fpath = folder / f"{slugify(evt['event_name'])}-scoring-data.json"
        if fpath.exists():
            LOG.info("%i %s data already exists...", evt["calendar_year"], evt["event_name"])
            continue
        score_data = collect_raw_event_data(evt)
        with open(fpath, "w") as outfile:
            json.dump(
                [asdict(event, value_serializer=serializer) for event in score_data],
                outfile,
                indent=4,
            )
