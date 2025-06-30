"""Data Golf API schemas."""

import inspect
from datetime import datetime
from types import UnionType
from typing import get_args, get_origin

import polars as pl
from attrs import define


def to_schema(obj) -> pl.Schema:
    """Create a Polars schema from an attrs object.

    Parameters
    ----------
    obj
        The class.

    Returns
    -------
    polars.Schema
        A polars schema.

    Examples
    --------
    At a basic level, converting a class to a schema is simple.

    >>> class MyClass:
    ...     def __init__(self, a: int):
    ...         self.a = a
    >>> to_schema(MyClass)
    Schema({'a': Int64})

    And the class works for datetimes as well.

    >>> from datetime import datetime
    >>> class MyClass:
    ...     def __init__(self, a: datetime):
    ...         self.a = a
    >>> to_schema(MyClass)
    Schema({'a': Datetime(time_unit='us', time_zone=None)})
    """
    out: dict[str, pl.DataType] = {}
    sig = inspect.signature(obj)
    for name, info in sig.parameters.items():
        if get_origin(info.annotation) == UnionType:
            # Get the first argument
            out[name] = pl.datatypes.DataType.from_python(get_args(info.annotation)[0])
        else:
            out[name] = pl.datatypes.DataType.from_python(info.annotation)

    return pl.Schema(out)


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
    sg_app: float
    sg_arg: float
    sg_ott: float
    sg_putt: float
    sg_t2g: float
    sg_total: float
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


@define(auto_attribs=True)
class ProperPlayerIndexDataset:
    """Proper Player Index (PPI) dataset schema."""

    dg_id: int
    player_name: str
    ppi: float
    teetime: datetime
    first_tee_time_in_group: datetime
    sg_total: float
    score: int
    event_name: str
    wave_average: float
    course_factor_star: float
    category: str
