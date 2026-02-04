"""
Vegetation Phenology Parameters (VPP) formatting utilities.

Converts raw TIMESAT VPP output arrays into human-readable tables
with formatted dates and rounded values.

Author: Zhanzhang Cai
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

import numpy as np

__all__ = [
    "vpp_to_table",
    "convert_vpp_day_to_date",
    "round_to_significant_digits",
]


def convert_vpp_day_to_date(value: Optional[float]) -> Optional[datetime]:
    """
    Convert a TIMESAT VPP day number to a calendar date.

    TIMESAT encodes dates as ``(year - 2000) * 1000 + day_of_year``.

    Parameters
    ----------
    value : float or None
        TIMESAT day number. If None, returns None.

    Returns
    -------
    datetime or None
        The corresponding calendar date, or None if invalid.
    """
    if value is None:
        return None
    try:
        year = int(value // 1000) + 2000
        day_of_year = value % 1000
        return datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
    except Exception:
        return None


def round_to_significant_digits(value: Any, digits: int = 4) -> Any:
    """
    Round a numeric value to a given number of significant digits.
    Dates are formatted as 'YYYY-MM-DD'.

    Parameters
    ----------
    value : any
        The value to format.
    digits : int
        Number of significant digits.

    Returns
    -------
    any
        Rounded number, formatted date string, or the original value.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return value
    if isinstance(value, (int, float)):
        return float(f"{value:.{digits}g}")
    if isinstance(value, (datetime, date)):
        d = value if isinstance(value, date) else value.date()
        return d.strftime("%Y-%m-%d")
    return value


def _format_date_columns(vpp_list: List[List]) -> List[List]:
    """Convert VPP day numbers in columns 0, 3, 8 to datetime objects."""
    for row in vpp_list:
        for col in [0, 3, 8]:
            if row[col] is not None:
                row[col] = convert_vpp_day_to_date(row[col])
    return vpp_list


def _format_significant(vpp_list: List[List]) -> List[List]:
    """Round all numeric values to significant digits."""
    for row in vpp_list:
        for i in range(len(row)):
            row[i] = round_to_significant_digits(row[i])
    return vpp_list


def vpp_to_table(
    vpp: np.ndarray,
    yrstart: int,
    nodata_out: float,
    fit_method_name: str,
) -> Tuple[List[List], List, List, List, List]:
    """
    Convert raw VPP array to a formatted table.

    Parameters
    ----------
    vpp : np.ndarray
        Raw VPP output from TIMESAT, shape (n_seasons * 13,) or similar.
    yrstart : int
        Start year of the time series.
    nodata_out : float
        NoData value used in VPP output.
    fit_method_name : str
        Name of the fitting method (e.g. 'DL', 'SP').

    Returns
    -------
    vpp_list : list[list]
        Formatted table rows. Each row starts with [method, period, ...].
    sos_x : list
        Start-of-season dates.
    sos_y : list
        Start-of-season values.
    eos_x : list
        End-of-season dates.
    eos_y : list
        End-of-season values.
    """
    vpp = vpp.copy()
    vpp[vpp == nodata_out] = np.nan
    vpp_reshaped = vpp.reshape(-1, 13)

    vpp_list = vpp_reshaped.tolist()
    vpp_list = [[None if np.isnan(x) else x for x in row] for row in vpp_list]
    vpp_list = _format_date_columns(vpp_list)

    sos_x = [row[0] for row in vpp_list]
    sos_y = [row[1] for row in vpp_list]
    eos_x = [row[3] for row in vpp_list]
    eos_y = [row[4] for row in vpp_list]

    vpp_list = _format_significant(vpp_list)

    # Add period labels: "2015-s1", "2015-s2", "2016-s1", ...
    periods = [f"{yrstart + i // 2}-s{i % 2 + 1}" for i in range(len(vpp_list))]
    for i in range(len(vpp_list)):
        vpp_list[i] = [periods[i]] + vpp_list[i]

    # Add method name column
    method_col = [fit_method_name] + ["" for _ in range(len(vpp_list) - 1)]
    for i in range(len(vpp_list)):
        vpp_list[i] = [method_col[i]] + vpp_list[i]

    return vpp_list, sos_x, sos_y, eos_x, eos_y
