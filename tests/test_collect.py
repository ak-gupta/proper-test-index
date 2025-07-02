"""Test the data collection module."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from proper_test_index.collect import collect_raw_event_data, retrieve_event_list
from proper_test_index.schemas import ScoreObject

CURR_DIR = Path(__file__).resolve().parent


@patch("requests.Session.get")
def test_retrieve_event_list(mock_req):
    """Test retrieving the event list."""
    # First, define the mock
    with open(CURR_DIR / "data" / "event-list.json") as infile:
        api_data = json.load(infile)
    mock_req.return_value = Mock(status_code=200, json=lambda: api_data)

    with patch.dict(os.environ, {}, clear=True):
        assert retrieve_event_list() == [
            {
                "calendar_year": 2021,
                "date": "2021-06-20",
                "event_id": 535,
                "event_name": "U.S. Open",
                "sg_categories": "yes",
                "traditional_stats": "yes",
                "tour": "pga",
            },
        ]


@patch("requests.Session.get")
def test_retrieve_raw_event_data(mock_req):
    """Test retrieving scoring data."""
    # First, define the mock
    with open(CURR_DIR / "data" / "scoring.json") as infile:
        api_data = json.load(infile)
    mock_req.return_value = Mock(status_code=200, json=lambda: api_data)

    expected = [
        ScoreObject(
            year=2021,
            event_id=535,
            event_name="U.S. Open",
            dg_id=19195,
            player_name="Rahm, Jon",
            round=1,
            course_name="Torrey Pines (South)",
            course_num=744,
            course_par=71,
            score=69,
            sg_app=0.35,
            sg_arg=0.94,
            sg_ott=1.92,
            sg_putt=1.51,
            sg_t2g=3.21,
            sg_total=4.718,
            driving_dist=311.5,
            driving_acc=0.714,
            teetime=datetime(2021, 6, 17, 15, 6, 0),
        ),
        ScoreObject(
            year=2021,
            event_id=535,
            event_name="U.S. Open",
            dg_id=19195,
            player_name="Rahm, Jon",
            round=2,
            course_name="Torrey Pines (South)",
            course_num=744,
            course_par=71,
            score=70,
            sg_app=1.26,
            sg_arg=1.3,
            sg_ott=-0.08,
            sg_putt=1.33,
            sg_t2g=2.48,
            sg_total=3.787,
            driving_dist=315.7,
            driving_acc=0.357,
            teetime=datetime(2021, 6, 18, 7, 51, 0),
        ),
        ScoreObject(
            year=2021,
            event_id=535,
            event_name="U.S. Open",
            dg_id=19195,
            player_name="Rahm, Jon",
            round=3,
            course_name="Torrey Pines (South)",
            course_num=744,
            course_par=71,
            score=72,
            sg_app=0.77,
            sg_arg=0.3,
            sg_ott=1.04,
            sg_putt=-1.7,
            sg_t2g=2.11,
            sg_total=0.408,
            driving_dist=316.8,
            driving_acc=0.429,
            teetime=datetime(2021, 6, 19, 13, 13, 0),
        ),
        ScoreObject(
            year=2021,
            event_id=535,
            event_name="U.S. Open",
            dg_id=19195,
            player_name="Rahm, Jon",
            round=4,
            course_name="Torrey Pines (South)",
            course_num=744,
            course_par=71,
            score=67,
            sg_app=2.61,
            sg_arg=-0.27,
            sg_ott=1.35,
            sg_putt=2.48,
            sg_t2g=3.69,
            sg_total=6.169,
            driving_dist=323.1,
            driving_acc=0.571,
            teetime=datetime(2021, 6, 20, 12, 22, 0),
        ),
    ]

    assert (
        collect_raw_event_data(
            {
                "calendar_year": 2021,
                "date": "2021-06-20",
                "event_id": 535,
                "event_name": "U.S. Open",
                "sg_categories": "yes",
                "traditional_stats": "yes",
                "tour": "pga",
            }
        )
        == expected
    )
