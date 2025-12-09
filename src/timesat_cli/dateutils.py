"""
Utility functions for handling date operations in TIMESAT processing.
"""

from __future__ import annotations

import datetime
import numpy as np

__all__ = ["date_with_ignored_day", "build_monthly_sample_indices"]


def is_leap_year(y: int) -> bool:
    """
    Return True if year y is a Gregorian leap year, False otherwise.
    """
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def date_with_ignored_day(yrstart: int, i_tv: int, p_ignoreday: int) -> datetime.date:
    """
    Convert a synthetic TIMESAT time index (1-based, assuming 365 days/year)
    into a real calendar date while skipping one day in leap years.
    """

    # ---- Step 1: synthetic 365-day calendar ----
    i = int(i_tv)
    year_offset, doy_365 = divmod(i - 1, 365)
    doy_365 += 1
    year = yrstart + year_offset

    jan1 = datetime.date(year, 1, 1)

    if is_leap_year(year):
        if not (1 <= p_ignoreday <= 366):
            raise ValueError("p_ignoreday must be in [1, 366] for leap years")

        if p_ignoreday == 1:
            real_ordinal = doy_365 + 1
        elif p_ignoreday == 366:
            real_ordinal = doy_365
        else:
            real_ordinal = doy_365 if doy_365 < p_ignoreday else doy_365 + 1
    else:
        real_ordinal = doy_365

    return jan1 + datetime.timedelta(days=real_ordinal - 1)


def build_monthly_sample_indices(yrstart: int, yr: int) -> np.ndarray:
    """
    Build a synthetic time index (1-based) for sampling the 1st, 11th, and 21st
    of each month across multiple years.

    The synthetic timeline always uses 365 days per year.
    In leap years we:
        - keep Feb 29
        - drop Dec 31
    so that each year still has 365 synthetic days.

    Parameters
    ----------
    yrstart : int
        Starting year of the period.

    yr : int
        Number of years to include.

    Returns
    -------
    np.ndarray
        A 1D array of indices into the synthetic timeline (1-based).
    """

    indices: list[int] = []
    year_offset = 0  # offset of each synthetic year start (0, 365, 730, ...)

    for year in range(yrstart, yrstart + yr):
        if is_leap_year(year):
            # Include Feb 29, drop Dec 31
            days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 30]
        else:
            days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        cum = 0  # cumulative day count within the current year

        for dim in days_in_month:
            for d in (1, 11, 21):
                if d <= dim:
                    indices.append(year_offset + cum + d)
            cum += dim

        year_offset += 365

    return np.array(indices, dtype=int)
