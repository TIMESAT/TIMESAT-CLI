"""
Single-pixel TIMESAT processing.

Provides functions to extract and process a single pixel from 3D arrays,
enabling interactive preview in the GUI without running batch processing.

Author: Zhanzhang Cai
"""

from __future__ import annotations

from datetime import datetime
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
    p_lowrangemode: np.ndarray | None = None,
    p_highrangemode: np.ndarray | None = None,
    p_rangedownweight: np.ndarray | None = None,
    time_sampling: str | None = None,
    time_step_days: int | None = None,
    monthly_days: List[int] | None = None,
    drop_first_year: bool = False,
    drop_last_year: bool = False,
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
    p_hrvppformat, p_seasonmethod, p_seapar, p_lowrangemode,
    p_highrangemode, p_rangedownweight :
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
    from .dateutils import date_with_ignored_day, generate_output_timeseries_dates
    from .qa import assign_qa_weight

    p_outindex, p_outindex_num = generate_output_timeseries_dates(
        p_outststep,
        nyear,
        yrstart,
        time_sampling=time_sampling,
        time_step_days=time_step_days,
        monthly_days=monthly_days,
        drop_first_year=drop_first_year,
        drop_last_year=drop_last_year,
    )

    # Replace NaN values with below-range value
    raw_y = np.nan_to_num(raw_y, nan=p_ylu[0] - 1)
    raw_w = assign_qa_weight(p_a, raw_w)

    lc = np.ones(raw_y.shape[:2], dtype=np.uint8)
    p_nclasses = 1
    landuse = np.ones(255, dtype="uint8")
    if p_lowrangemode is None:
        p_lowrangemode = np.zeros(255, dtype=np.int32)
    else:
        p_lowrangemode = np.asarray(p_lowrangemode, dtype=np.int32)
    if p_highrangemode is None:
        p_highrangemode = np.zeros(255, dtype=np.int32)
    else:
        p_highrangemode = np.asarray(p_highrangemode, dtype=np.int32)
    if p_rangedownweight is None:
        p_rangedownweight = np.full(255, 0.5, dtype=np.float64)
    else:
        p_rangedownweight = np.asarray(p_rangedownweight, dtype=np.float64)

    vpp, vppqa, nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
        nyear, raw_y, raw_w, tv_yyyydoy, lc,
        p_nclasses, landuse, p_outindex,
        p_ignoreday, p_ylu, p_printflag, p_fitmethod, p_smooth,
        p_nodata, p_davailwin, p_outlier,
        p_nenvi, p_wfactnum, p_startmethod, p_startcutoff,
        p_low_percentile, p_fillbase, p_hrvppformat,
        p_seasonmethod, p_seapar,
        p_lowrangemode, p_highrangemode, p_rangedownweight,
        1, 1, 1, npt, p_outindex_num,
    )

    daily_timestep = [
        datetime.combine(date_with_ignored_day(yrstart, int(i), p_ignoreday), datetime.min.time())
        for i in p_outindex
    ]

    return vpp, vppqa, nseason, yfit, yfitqa, seasonfit, daily_timestep
