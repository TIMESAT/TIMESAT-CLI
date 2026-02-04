"""
Single-pixel TIMESAT processing.

Provides functions to extract and process a single pixel from 3D arrays,
enabling interactive preview in the GUI without running batch processing.

Author: Zhanzhang Cai
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np

__all__ = [
    "extract_single_pixel",
    "run_single_pixel",
]


def extract_single_pixel(
    row: int,
    col: int,
    ym3: np.ndarray,
    wm3: np.ndarray,
    lc3: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract data for a single pixel from 3D arrays.

    Parameters
    ----------
    row : int
        Row index (0-based).
    col : int
        Column index (0-based).
    ym3 : np.ndarray
        Data cube, shape (rows, cols, time).
    wm3 : np.ndarray
        Quality/weight cube, shape (rows, cols, time).
    lc3 : np.ndarray
        Land cover array, shape (rows, cols).

    Returns
    -------
    raw_y : np.ndarray
        Data values, shape (1, 1, time).
    raw_w : np.ndarray
        Weight values, shape (1, 1, time).
    raw_lc : np.ndarray
        Land cover value, shape (1, 1).
    """
    raw_y = ym3[row:row + 1, col:col + 1, :]
    raw_w = wm3[row:row + 1, col:col + 1, :]
    raw_lc = lc3[row:row + 1, col:col + 1]
    return raw_y, raw_w, raw_lc


def run_single_pixel(
    raw_y: np.ndarray,
    raw_w: np.ndarray,
    raw_lc: np.ndarray,
    tv_yyyydoy: np.ndarray,
    yrstart: int,
    nyear: int,
    npt: int,
    p_outststep: int,
    p_ignoreday: int,
    p_ylu: List[float],
    p_a: List[float],
    p_printflag: int,
    p_fitmethod: np.ndarray,
    p_smooth: np.ndarray,
    p_nodata: float,
    p_davailwin: int,
    p_outlier: int,
    p_nenvi: np.ndarray,
    p_wfactnum: np.ndarray,
    p_startmethod: np.ndarray,
    p_startcutoff: np.ndarray,
    p_low_percentile: np.ndarray,
    p_fillbase: np.ndarray,
    p_hrvppformat: int,
    p_seasonmethod: np.ndarray,
    p_seapar: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[datetime]]:
    """
    Run TIMESAT fitting on a single pixel.

    Parameters
    ----------
    raw_y : np.ndarray
        Data values, shape (1, 1, time).
    raw_w : np.ndarray
        Weight values, shape (1, 1, time).
    raw_lc : np.ndarray
        Land cover value, shape (1, 1).
    tv_yyyydoy : np.ndarray
        Time vector in YYYYDOY format.
    yrstart : int
        Start year.
    nyear : int
        Number of years.
    npt : int
        Number of data points (time steps).
    p_outststep : int
        Output time step.
    p_ignoreday, p_ylu, p_a, p_printflag, p_fitmethod, p_smooth,
    p_nodata, p_davailwin, p_outlier, p_nenvi, p_wfactnum,
    p_startmethod, p_startcutoff, p_low_percentile, p_fillbase,
    p_hrvppformat, p_seasonmethod, p_seapar :
        TIMESAT algorithm parameters.

    Returns
    -------
    vpp : np.ndarray
        Vegetation phenology parameters.
    vppqa : np.ndarray
        VPP quality flags.
    nseason : np.ndarray
        Number of seasons per year.
    yfit : np.ndarray
        Fitted time series.
    yfitqa : np.ndarray
        Fit quality flags.
    seasonfit : np.ndarray
        Coarse season fit.
    daily_timestep : list[datetime]
        Daily time steps for the fitted series.
    """
    import timesat

    p_outindex = np.arange(1, nyear * 365 + 1)[::p_outststep]
    p_outindex_num = len(p_outindex)

    # Replace NaN values with below-range value
    raw_y = np.nan_to_num(raw_y, nan=p_ylu[0] - 1)

    lc = np.ones(raw_y.shape[:2], dtype=np.uint8)
    p_nclasses = 1
    landuse = np.ones(255, dtype="uint8")

    vpp, vppqa, nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
        nyear, raw_y, raw_w, tv_yyyydoy, lc,
        p_nclasses, landuse, p_outindex,
        p_ignoreday, p_ylu, p_printflag, p_fitmethod, p_smooth,
        p_nodata, p_davailwin, p_outlier,
        p_nenvi, p_wfactnum, p_startmethod, p_startcutoff,
        p_low_percentile, p_fillbase, p_hrvppformat,
        p_seasonmethod, p_seapar,
        1, 1, 1, npt, p_outindex_num,
    )

    daily_timestep = []
    for year in range(yrstart, yrstart + nyear):
        for day in range(365):
            daily_timestep.append(datetime(year, 1, 1) + timedelta(days=day))
    daily_timestep = daily_timestep[::p_outststep]

    return vpp, vppqa, nseason, yfit, yfitqa, seasonfit, daily_timestep
