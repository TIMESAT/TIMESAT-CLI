"""
Table (CSV/Excel) data reader for TIMESAT processing.

Reads tabular time-series data where the first column is dates
and remaining columns are data series (e.g. NDVI values for different pixels).

Author: Zhanzhang Cai
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd

__all__ = [
    "TableData",
    "read_table_data",
]


@dataclass
class TableData:
    """Result of reading table data."""

    ym3: np.ndarray          # Data cube, shape (n_series, 1, n_time)
    wm3: np.ndarray          # Weights, shape (n_series, 1, n_time)
    lc3: np.ndarray          # Land cover, shape (n_series, 1)
    tv_yyyymmdd: np.ndarray  # Time vector in YYYYMMDD format
    tv_yyyydoy: np.ndarray   # Time vector in YYYYDOY format
    min_date: str             # Min date as 'YYYY-MM-DD'
    max_date: str             # Max date as 'YYYY-MM-DD'
    min_y: float              # Min data value
    max_y: float              # Max data value
    nyear: int                # Number of years
    yrstart: int              # Start year
    yrend: int                # End year


def read_table_data(df: pd.DataFrame) -> TableData:
    """
    Read table data (CSV/Excel) into arrays for TIMESAT processing.

    The first column must contain dates (parseable by ``pd.to_datetime``).
    All remaining columns are treated as separate data series.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe. First column = dates, remaining = data values.

    Returns
    -------
    TableData
        Parsed arrays and metadata ready for TIMESAT processing.
    """
    first_col_name = df.columns[0]

    # Parse dates
    dates = pd.to_datetime(df[first_col_name])
    tv_yyyydoy = dates.dt.strftime("%Y%j").tolist()
    tv_yyyymmdd = dates.dt.strftime("%Y%m%d").tolist()

    npt = len(df)
    n_series = df.shape[1] - 1  # all columns except date

    # Build 3D arrays: (n_series, 1, n_time)
    ym3 = np.zeros((n_series, 1, npt), dtype=np.float32)
    wm3 = np.ones((n_series, 1, npt), dtype=np.float32)
    lc3 = np.ones((n_series, 1), dtype=np.float32)

    # Fill data from columns 1..end
    ym3[:, 0, :] = df.iloc[:, 1:].T.values.astype(np.float32)

    # Convert to numpy arrays
    tv_yyyymmdd = np.array(tv_yyyymmdd, dtype=int)
    tv_yyyydoy = np.array(tv_yyyydoy, dtype=int)

    # Year range
    yv = tv_yyyymmdd // 10000
    yrstart = int(np.min(yv))
    yrend = int(np.max(yv))
    nyear = yrend - yrstart + 1

    # Date range strings
    min_t = str(tv_yyyymmdd.min())
    max_t = str(tv_yyyymmdd.max())
    min_date = f"{min_t[:4]}-{min_t[4:6]}-{min_t[6:]}"
    max_date = f"{max_t[:4]}-{max_t[4:6]}-{max_t[6:]}"

    min_y = float(np.nanmin(ym3))
    max_y = float(np.nanmax(ym3))

    return TableData(
        ym3=ym3,
        wm3=wm3,
        lc3=lc3,
        tv_yyyymmdd=tv_yyyymmdd,
        tv_yyyydoy=tv_yyyydoy,
        min_date=min_date,
        max_date=max_date,
        min_y=min_y,
        max_y=max_y,
        nyear=nyear,
        yrstart=yrstart,
        yrend=yrend,
    )
