"""
CSV / table utilities for TIMESAT processing.

- ``read_timeseries_csv``: single-site CSV with fixed columns (time, vi, qa).
- ``read_table_data``:     multi-series DataFrame (first col = dates, rest = data).
- ``write_timesat_csv_outputs``: write yfit / vpp / nseason CSVs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import datetime as dt

import numpy as np
import pandas as pd

__all__ = [
    "read_timeseries_csv",
    "write_timesat_csv_outputs",
    "TableData",
    "read_table_data",
]


# ---------------------------------------------------------------------------
# Single-site CSV  (existing)
# ---------------------------------------------------------------------------

def _parse_time_column(col: Iterable[str | int]) -> np.ndarray:
    """
    Accepts YYYYDOY (e.g., 2020123) or YYYYMMDD (e.g., 20200123) or ISO 'YYYY-MM-DD'.
    Returns uint32 vector in YYYYDOY.
    """
    out = []
    for v in col:
        s = str(v)
        if len(s) == 7:  # YYYYDOY
            # will raise if invalid
            dt.datetime.strptime(s, "%Y%j")
            out.append(int(s))
        elif len(s) == 8 and s.isdigit():  # YYYYMMDD
            d = dt.datetime.strptime(s, "%Y%m%d")
            out.append(int(f"{d.year}{d.timetuple().tm_yday:03d}"))
        else:  # try ISO
            try:
                d = dt.datetime.strptime(s, "%Y-%m-%d")
                out.append(int(f"{d.year}{d.timetuple().tm_yday:03d}"))
            except Exception as e:
                raise ValueError(f"Unrecognized date format: {s}") from e
    return np.array(out, dtype="uint32")


def read_timeseries_csv(path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Read a per-site (single pixel) time series CSV.

    Expected columns:
      - 'time'      : YYYYDOY or YYYYMMDD or YYYY-MM-DD
      - 'vi'        : vegetation index values (float)
      - 'qa'        : optional; quality or weights (float/int). If missing, set to 1.
      - 'lc'        : optional; land cover code (int). If missing, set to 1.

    Returns:
      vi  : array shaped (1, 1, T)
      qa  : array shaped (1, 1, T)
      timevector : 1-D uint32 YYYYDOY of length T
    """
    df = pd.read_csv(path)
    if "time" not in df or "vi" not in df:
        raise ValueError("CSV must contain at least 'time' and 'vi' columns.")
    timevector = _parse_time_column(df["time"])
    vi = df["vi"].to_numpy(dtype="float64")
    qa = df["qa"].to_numpy(dtype="float64") if "qa" in df else np.ones_like(vi, dtype="float64")
    # shape to (y=1, x=1, z=T)
    vi = vi.reshape(1, 1, -1, order="F")
    qa = qa.reshape(1, 1, -1, order="F")
    return vi, qa, timevector


def write_timesat_csv_outputs(
    out_folder: str,
    timevector_out: np.ndarray,   # p_outindex dates in YYYYDOY
    yfit: np.ndarray,             # shape (T_out,) for single site
    vpp: Optional[np.ndarray],    # shape (13*2*yr,) flattened for single site
    nseason: Optional[int]
) -> None:
    """
    Writes three CSVs:
      - yfit.csv: columns [time(YYYYDOY), yfit]
      - vpp.csv : 13*2*yr parameters as columns VPP_1 ... VPP_N (optional if vpp is None)
      - nseason.csv: single row with nseason (optional if nseason is None)
    """
    import os
    os.makedirs(out_folder, exist_ok=True)

    # yfit
    yfit_df = pd.DataFrame({
        "time": timevector_out.astype("uint32"),
        "yfit": yfit.astype("float64")
    })
    yfit_df.to_csv(os.path.join(out_folder, "yfit.csv"), index=False)

    # vpp
    if vpp is not None:
        vpp = vpp.ravel(order="F").astype("float64")
        cols = [f"VPP_{i+1}" for i in range(vpp.size)]
        vpp_df = pd.DataFrame([vpp], columns=cols)
        vpp_df.to_csv(os.path.join(out_folder, "vpp.csv"), index=False)

    # nseason
    if nseason is not None:
        pd.DataFrame({"nseason": [int(nseason)]}).to_csv(
            os.path.join(out_folder, "nseason.csv"), index=False
        )


# ---------------------------------------------------------------------------
# Multi-series table reader  (from GUI, merged here)
# ---------------------------------------------------------------------------

@dataclass
class TableData:
    """Result of reading multi-series table data."""

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
    Read multi-series table data (CSV/Excel DataFrame) into arrays
    for TIMESAT processing.

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

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.read_csv("timeseries.csv")
    >>> result = read_table_data(df)
    >>> result.ym3.shape  # (n_series, 1, n_time)
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
