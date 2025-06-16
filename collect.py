# /// script
# dependencies = [
#     "python-dotenv",
#     "requests",
#     "urllib3",
# ]
# ///

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
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


class ScoreObject(TypedDict):
    """Scoring object.

    Defines the attributes for raw player/round-level scoring.
    """

    year: int
    dg_id: int
    player_name: str
    round: int
    course_name: str
    course_num: int
    course_par: int
    score: int
    teetime: datetime


class CourseInfo(TypedDict):
    """Course information.

    Used in conjunction with the NOAA weather service to get approximate weather conditions
    for a given round.
    """

    course_name: str
    course_num: int
    latitude: float
    longitude: float
    location: str


def retrieve_event_list() -> list[tuple[int, int]]:
    """Get the list of US Open event IDs.

    Returns
    -------
    list[tuple[int, int]]
        A list of tuples. The first entry in the tuple is the year of the event,
        the second entry is the event ID in DataGolf's database.
    """
    LOG.info("Retrieving list of events...")
    response_ = SESSION.get(
        f"{BASE_URL}/historical-raw-data/event-list",
        params={"file_format": "json", "key": os.getenv("API_TOKEN")},
    )
    response_.raise_for_status()
    out: list[tuple[int, int]] = []
    for itm in response_.json():
        if itm["event_name"] == "U.S. Open":  # TODO: fix
            out.append((itm["calendar_year"], itm["event_id"]))

    return out


def collect_raw_event_data(events: list[tuple[int, int]]) -> list[ScoreObject]:
    """Collect raw event data.

    Parameters
    ----------
    events : list[tuple[int, int]]
        The list of events to pull. The first entry in the list is the year of the event,
        the second entry is the event ID.

    Returns
    -------
    list[ScoreObject]
        A list of round-level scores.
    """
    out: list[ScoreObject] = []
    for year, event_id in events:
        LOG.info("Retrieving scores for the %i U.S. Open (%i)", year, event_id)
        response_ = SESSION.get(
            f"{BASE_URL}/historical-raw-data/rounds",
            params={
                "tour": "pga",
                "event_id": event_id,
                "year": year,
                "file_format": "json",
                "key": os.getenv("API_TOKEN"),
            },
        )
        response_.raise_for_status()
        LOG.info("Successfully retrieved %i U.S. Open scores")
        for player in response_.json()["scores"]:
            for i in range(1, 5):  # Each round
                out += [
                    ScoreObject(
                        year=year,
                        dg_id=player["dg_id"],
                        player_name=player["player_name"],
                        round=i,
                        course_name=player[f"round_{i!s}"]["course_name"],
                        course_num=player[f"round_{i!s}"]["course_num"],
                        course_par=player[f"round_{i!s}"]["course_par"],
                        score=player[f"round_{i!s}"]["score"],
                        teetime=datetime.strptime(
                            player[f"round_{i!s}"]["teetime"], "%I:%M%p"
                        ),
                    )
                ]

    return out


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    # Load the dotenv file
    load_dotenv(CURR_DIR / ".env")

    events = retrieve_event_list()
    score_data = collect_raw_event_data(events)

    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "scoring-data.json", "w") as outfile:
        json.dump(score_data, outfile, indent=4)
