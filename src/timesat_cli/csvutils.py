# csvutils.py
from __future__ import annotations
from typing import Tuple, Iterable, Optional
import numpy as np
import pandas as pd
import datetime as dt

__all__ = ["read_timeseries_csv", "write_timesat_csv_outputs"]

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
