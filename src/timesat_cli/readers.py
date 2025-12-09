from __future__ import annotations

import datetime
import os
import re

import numpy as np
import rasterio
from rasterio.windows import Window

from .qa import assign_qa_weight

__all__ = ["read_file_lists", "open_image_data"]

def _parse_dates_from_name(name: str) -> tuple[int, int, int]:
    date_regex1 = r"\d{4}-\d{2}-\d{2}"
    date_regex2 = r"\d{4}\d{2}\d{2}"
    try:
        dates = re.findall(date_regex1, name)
        position = name.find(dates[0])
        y = int(name[position : position + 4])
        m = int(name[position + 5 : position + 7])
        d = int(name[position + 8 : position + 10])
        return y, m, d
    except Exception:
        try:
            dates = re.findall(date_regex2, name)
            position = name.find(dates[0])
            y = int(name[position : position + 4])
            m = int(name[position + 4 : position + 6])
            d = int(name[position + 6 : position + 8])
            return y, m, d
        except Exception as e:
            raise ValueError(f"No date found in filename: {name}") from e


def _read_time_vector(tlist: str, filepaths: list[str]):
    """Return (timevector, yr, yrstart, yrend) in YYYYDOY format."""
    flist = [os.path.basename(p) for p in filepaths]
    timevector = np.ndarray(len(flist), order="F", dtype="uint32")
    if tlist == "":
        for i, fname in enumerate(flist):
            y, m, d = _parse_dates_from_name(fname)
            doy = (datetime.date(y, m, d) - datetime.date(y, 1, 1)).days + 1
            timevector[i] = y * 1000 + doy
    else:
        with open(tlist, "r") as f:
            lines = f.read().splitlines()
        for idx, val in enumerate(lines):
            n = len(val)
            if n == 8:  # YYYYMMDD
                dt = datetime.datetime.strptime(val, "%Y%m%d")
                timevector[idx] = int(f"{dt.year}{dt.timetuple().tm_yday:03d}")
            elif n == 7:  # YYYYDOY
                _ = datetime.datetime.strptime(val, "%Y%j")
                timevector[idx] = int(val)
            else:
                raise ValueError(f"Unrecognized date format: {val}")

    yrstart = int(np.floor(timevector.min() / 1000))
    yrend = int(np.floor(timevector.max() / 1000))
    yr = yrend - yrstart + 1
    return timevector, yr, yrstart, yrend


def _unique_by_timevector(flist: list[str], qlist: list[str], timevector):
    tv_unique, indices = np.unique(timevector, return_index=True)
    flist2 = [flist[i] for i in indices]
    qlist2 = [qlist[i] for i in indices] if qlist else []
    return tv_unique, flist2, qlist2


def read_file_lists(
    tlist: str, data_list: str, qa_list: str
) -> tuple[np.ndarray, list[str], list[str], int, int, int]:
    qlist: list[str] | str = ""
    with open(data_list, "r") as f:
        flist = f.read().splitlines()
    if qa_list != "":
        with open(qa_list, "r") as f:
            qlist = f.read().splitlines()
        if len(flist) != len(qlist):
            raise ValueError("No. of Data and QA are not consistent")

    timevector, yr, yrstart, yrend = _read_time_vector(tlist, flist)
    timevector, flist, qlist = _unique_by_timevector(flist, qlist, timevector)
    return (
        timevector,
        flist,
        (qlist if isinstance(qlist, list) else []),
        yr,
        yrstart,
        yrend,
    )

def open_image_data(
    x_map: int,
    y_map: int,
    x: int,
    y: int,
    data_datasets: list,
    qa_datasets: list,
    lc_dataset,
    data_type: str,
    p_a,
    layer: int,
):
    """
    Read VI, QA, and LC blocks using already-open rasterio datasets.
    This is fast because we do NOT call rasterio.open() for each block.
    """

    z = len(data_datasets)

    # allocate arrays
    vi = np.ndarray((y, x, z), order="F", dtype=data_type)
    qa = np.ndarray((y, x, z), order="F", dtype=data_type)
    lc = np.ndarray((y, x), order="F", dtype=np.uint8)

    win = Window(x_map, y_map, x, y)

    # -----------------------------------------------------------
    # 1) Read VI stack
    # -----------------------------------------------------------
    for i, ds in enumerate(data_datasets):
        arr = ds.read(layer, window=win)
        if arr.ndim == 3:
            arr = arr[0, :, :]
        vi[:, :, i] = arr

    # -----------------------------------------------------------
    # 2) Read QA stack (or fill with ones)
    # -----------------------------------------------------------
    if len(qa_datasets) == 0:
        qa[:] = 1
    else:
        for i, ds in enumerate(qa_datasets):
            arr = ds.read(layer, window=win)
            if arr.ndim == 3:
                arr = arr[0, :, :]
            qa[:, :, i] = arr

        # Weight QA
        from .qa import assign_qa_weight
        qa = assign_qa_weight(p_a, qa)

    # -----------------------------------------------------------
    # 3) Land cover (single layer)
    # -----------------------------------------------------------
    if lc_dataset is None:
        lc[:] = 1
    else:
        arr = lc_dataset.read(1, window=win)
        if arr.ndim == 3:
            arr = arr[0, :, :]
        lc[:, :] = arr.astype(np.uint8)

    return vi, qa, lc

