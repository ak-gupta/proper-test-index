"""Data collection module."""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from proper_test_index.schemas import ScoreObject

LOG = logging.getLogger(__name__)

CURR_DIR = Path(__file__).resolve().parent
DATA_DIR = CURR_DIR / "data"

SESSION = requests.Session()
RETRIES = Retry(total=10, backoff_factor=2, status_forcelist=[502, 503, 504])
ADAPTER = HTTPAdapter(max_retries=RETRIES)
SESSION.mount("http://", ADAPTER)
SESSION.mount("https://", ADAPTER)

BASE_URL = "https://feeds.datagolf.com"


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
    LOG.info(
        "Retrieving scores for the %i %s (%i)",
        event["calendar_year"],
        event["event_name"],
        event["event_id"],
    )
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
    LOG.info(
        "Successfully retrieved %i %s scores",
        event["calendar_year"],
        event["event_name"],
    )
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
                    sg_app=round_data.get("sg_app"),
                    sg_arg=round_data.get("sg_arg"),
                    sg_ott=round_data.get("sg_ott"),
                    sg_putt=round_data.get("sg_putt"),
                    sg_t2g=round_data.get("sg_t2g"),
                    sg_total=round_data.get("sg_total"),
                )
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

                if (teetime := round_data.get("teetime")) is not None:
                    parsed_teetime = datetime.strptime(teetime, "%I:%M%p")
                    obj.teetime = datetime(
                        round_date.year,
                        round_date.month,
                        round_date.day,
                        parsed_teetime.hour,
                        parsed_teetime.minute,
                        0,
                    )
                else:
                    obj.teetime = round_date

                out.append(obj)

    return out
