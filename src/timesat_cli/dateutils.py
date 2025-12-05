"""
Utility functions for handling date operations in TIMESAT processing.
"""

from __future__ import annotations
import datetime
import calendar

__all__ = ["date_with_ignored_day"]

def date_with_ignored_day(yrstart: int, i_tv: int, p_ignoreday: int) -> datetime.date:
    """
    Convert a synthetic TIMESAT time index (1-based, assuming 365 days/year)
    into a real calendar date while skipping one day in leap years.

    This is needed because TIMESAT internally forces every year to have
    365 days. During leap years, one real calendar day (p_ignoreday) must
    be skipped so that synthetic DOY aligns with actual dates.

    Parameters
    ----------
    yrstart : int
        The starting year of the TIMESAT time series.

    i_tv : int
        1-based absolute index into a synthetic timeline, where each
        synthetic year has exactly 365 days. Example:
            i_tv = 1   -> first day of yrstart
            i_tv = 366 -> first day of yrstart + 1

    p_ignoreday : int
        The real calendar day-of-year (1–366) to skip in leap years.
        Examples:
            366 -> skip Dec 31 in leap years
            1   -> skip Jan 1 (so synthetic day 1 maps to Jan 2)
            A value 2–365 skips an interior date.

    Returns
    -------
    datetime.date
        The mapped real-world calendar date.
    """

    # ---- Step 1: Convert 1-based synthetic index into year + 1..365 DOY ----
    i = int(i_tv)
    year_offset, doy_365 = divmod(i - 1, 365)
    doy_365 += 1
    year = yrstart + year_offset

    # ---- Step 2: Handle leap-year day skipping ----
    jan1 = datetime.date(year, 1, 1)

    if calendar.isleap(year):
        if not (1 <= p_ignoreday <= 366):
            raise ValueError("p_ignoreday must be within [1, 366] for leap years")

        if p_ignoreday == 1:
            # Skip Jan 1 → shift all synthetic DOY forward by +1
            real_ordinal = doy_365 + 1
        elif p_ignoreday == 366:
            # Skip Dec 31 → synthetic matches real ordinal for 1..365
            real_ordinal = doy_365
        else:
            # Skip an interior day; all days ≥ skip_day shift by +1
            real_ordinal = doy_365 if doy_365 < p_ignoreday else doy_365 + 1
    else:
        # Non-leap year: direct mapping
        real_ordinal = doy_365

    # ---- Step 3: Convert day-of-year to actual date ----
    return jan1 + datetime.timedelta(days=real_ordinal - 1)
