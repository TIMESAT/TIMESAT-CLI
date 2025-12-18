from __future__ import annotations

import datetime
import os
import re

import numpy as np
import rasterio
from rasterio.windows import Window

from .qa import assign_qa_weight

__all__ = ["read_file_lists", "open_image_data","open_image_data_batched"]

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
    data_files: list[str],
    qa_files: list[str],
    lc_file: str | None,
    data_type: str,
    p_a,
    layer: int,
):
    """
    Open each raster, read the window immediately, and close it.
    Suitable for local paths or presigned HTTPS URLs.

    NOTE: This does not use rasterio.Env (AWS options blocked in your env).
    """
    z = len(data_files)
    if qa_files and len(qa_files) != z:
        raise ValueError(f"qa_files length ({len(qa_files)}) must match data_files length ({z})")

    win = Window(x_map, y_map, x, y)

    # Allocate final outputs
    vi = np.empty((y, x, z), order="F", dtype=data_type)
    qa = np.empty((y, x, z), order="F", dtype=data_type)
    lc = np.empty((y, x), order="F", dtype=np.uint8)

    # 1) VI: open -> read -> close (per file)
    for i, path in enumerate(data_files):
        with rasterio.open(path, "r") as ds:
            # Read returns (y, x) when a single band is selected
            vi[:, :, i] = ds.read(layer, window=win)

    # 2) QA: open -> read -> close (per file), or fill with ones
    if not qa_files:
        qa.fill(1)
    else:
        for i, path in enumerate(qa_files):
            with rasterio.open(path, "r") as ds:
                # QA is commonly band 1; change if needed
                qa[:, :, i] = ds.read(1, window=win)
        print('data read')
        qa = assign_qa_weight(p_a, qa)

    # 3) LC: open -> read -> close (once)
    if not lc_file:
        lc.fill(1)
    else:
        with rasterio.open(lc_file, "r") as ds:
            lc[:, :] = ds.read(1, window=win)
        if lc.dtype != np.uint8:
            lc[:] = lc.astype(np.uint8, copy=False)

    return vi, qa, lc


def open_image_data_batched(
    x_map: int,
    y_map: int,
    x: int,
    y: int,
    data_files: list[str],
    qa_files: list[str],
    lc_file: str | None,
    data_type: str,
    p_a,
    layer: int,
    batch_size: int = 32,
    s3_opts: dict | None = None,  # kept for API compatibility, but NOT used
):
    """
    Read VI, QA, and LC blocks by opening datasets in small batches.

    IMPORTANT:
    - Do NOT use rasterio.Env(AWS_...) in this environment (blocked).
    - For S3/S3-compatible, pass presigned HTTPS URLs in data_files/qa_files/lc_file.
    """

    z = len(data_files)
    if qa_files and len(qa_files) != z:
        raise ValueError(f"qa_files length ({len(qa_files)}) must match data_files length ({z})")

    vi = np.empty((y, x, z), order="F", dtype=data_type)
    qa = np.empty((y, x, z), order="F", dtype=data_type)
    lc = np.empty((y, x), order="F", dtype=np.uint8)

    win = Window(x_map, y_map, x, y)
    def _read_stack(paths: list[str], out_arr: np.ndarray, band: int):
        for j0 in range(0, z, batch_size):
            j1 = min(z, j0 + batch_size)
            dss = [rasterio.open(p, "r") for p in paths[j0:j1]]
            try:
                for k, ds in enumerate(dss):
                    ds.read(band, window=win, out=out_arr[:, :, j0 + k])
            finally:
                for ds in dss:
                    try:
                        ds.close()
                    except Exception:
                        pass

    # 1) VI
    _read_stack(data_files, vi, band=layer)

    # 2) QA
    if not qa_files:
        qa.fill(1)
    else:
        # QA is usually band 1; change if your QA files differ
        _read_stack(qa_files, qa, band=1)
        qa = assign_qa_weight(p_a, qa)

    # 3) LC
    if not lc_file:
        lc.fill(1)
    else:
        with rasterio.open(lc_file, "r") as ds:
            ds.read(1, window=win, out=lc)
        if lc.dtype != np.uint8:
            lc[:] = lc.astype(np.uint8, copy=False)

    return vi, qa, lc

