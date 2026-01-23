from __future__ import annotations

import datetime
import os
import re

import numpy as np
import rasterio
from rasterio.windows import Window

__all__ = ["read_time_vector_data", "read_file_lists", "open_image_data"]


def read_time_vector_data(lines):
    """
    Extract dates from band names (strings in `lines`).

    Returns:
        tv_yyyymmdd (np.ndarray, dtype=object): [YYYYMMDD or None, ...]
        tv_yyyydoy  (np.ndarray, dtype=object): [YYYYDOY  or None, ...]
        nyear       (int or None): number of years covered (inclusive)
        yrstart     (int or None): first year
        yrend       (int or None): last year
    """
    # Precompile patterns once
    patterns = [
        re.compile(r"(\d{4})(\d{2})(\d{2})"),          # YYYYMMDD
        re.compile(r"(\d{4})(\d{3})"),                 # YYYYDOY
        re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})"),  # YYYY-MM-DD or YYYY_MM_DD
        re.compile(r"(\d{4})[-_](\d{3})"),             # YYYY-DOY or YYYY_DOY
    ]

    def parse_date(text):
        """Return a datetime.date if a supported pattern is found; else None."""
        for pat in patterns:
            m = pat.search(text)
            if not m:
                continue

            g = m.groups()
            try:
                if len(g) == 3:  # YYYY MM DD
                    year, month, day = map(int, g)
                    return datetime.datetime(year, month, day).date()

                # len(g) == 2: YYYY + DOY
                year = int(g[0])
                doy = int(g[1])
                if 1 <= doy <= 366:  # basic sanity
                    return (datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1)).date()
            except ValueError:
                return None

        return None

    # Build lists aligned to `lines`
    yyyymmdd_list = []
    yyyydoy_list = []

    for name in lines:
        d = parse_date(str(name))
        if d is None:
            yyyymmdd_list.append(None)
            yyyydoy_list.append(None)
        else:
            yyyymmdd_list.append(int(d.strftime("%Y%m%d")))
            yyyydoy_list.append(int(d.strftime("%Y%j")))

    # Use dtype=object to preserve None
    tv_yyyymmdd = np.array(yyyymmdd_list, order="F", dtype="uint32")
    tv_yyyydoy = np.array(yyyydoy_list, order="F", dtype="uint32")

    # Compute year stats from valid entries only
    valid_years = [v // 10000 for v in tv_yyyymmdd if v is not None]
    if not valid_years:
        return tv_yyyymmdd, tv_yyyydoy, None, None, None

    yrstart = int(min(valid_years))
    yrend = int(max(valid_years))
    nyear = yrend - yrstart + 1

    return tv_yyyymmdd, tv_yyyydoy, nyear, yrstart, yrend



def _read_time_vector(tlist: str, filepaths: list[str]):
    """Return (timevector, yr, yrstart, yrend) in YYYYDOY format."""
    flist = [os.path.basename(p) for p in filepaths]
    if tlist == "":
        lines = flist
    else:
        with open(tlist, "r") as f:
            lines = f.read().splitlines()
    
    tv_yyyymmdd, timevector, yr, yrstart, yrend = read_time_vector_data(lines)

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
    timevector, yr, yrstart, yrend = _read_time_vector(tlist, flist)

    if qa_list != "":
        with open(qa_list, "r") as f:
            qlist = f.read().splitlines()
        if len(flist) != len(qlist):
            raise ValueError("No. of Data and QA are not consistent")
        timevector_q, yr_q, yrstart_q, yrend_q = _read_time_vector("", qlist)

        # Check if timevector and timevector_q are the same, otherwise align QA to data timeline
        if not (len(timevector) == len(timevector_q) and np.array_equal(timevector, timevector_q)):

            # Map QA timestamps -> QA path
            qa_map: dict[float, str] = {float(t): p for t, p in zip(timevector_q, qlist)}

            aligned_qlist: list[str] = []
            missing_times: list[float] = []

            for t in timevector:
                key = float(t)
                if key in qa_map:
                    aligned_qlist.append(qa_map[key])
                else:
                    aligned_qlist.append("")  # placeholder
                    missing_times.append(key)

            if missing_times:
                raise ValueError(
                    "QA list does not cover all data timestamps. Missing QA for "
                    f"{len(missing_times)} timestamps (first 10 shown): {missing_times[:10]}"
                )

            qlist = aligned_qlist

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
    data_type: str | None,
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

    if data_type is None:
        with rasterio.open(data_files[0], "r") as ds:
            data_type = np.dtype(ds.dtypes[layer - 1])
    else:
        data_type = np.dtype(data_type)
        
    # Allocate final outputs
    vi = np.empty((y, x, z), order="F", dtype=data_type)
    qa = np.empty((y, x, z), order="F", dtype=data_type)
    lc = np.empty((y, x), order="F", dtype=np.uint8)

    # 1) VI: open -> read -> close (per file)
    for i, path in enumerate(data_files):
        with rasterio.open(path, "r") as ds:
            # Read returns (y, x) when a single band is selected
            vi[:, :, i] = ds.read(layer, window=win, out_dtype=vi.dtype)

    # 2) QA: open -> read -> close (per file), or fill with ones
    if not qa_files:
        qa.fill(1)
    else:
        for i, path in enumerate(qa_files):
            with rasterio.open(path, "r") as ds:
                # QA is commonly band 1; change if needed
                qa[:, :, i] = ds.read(1, window=win, out_dtype=qa.dtype)
        print('data read')

    # 3) LC: open -> read -> close (once)
    if not lc_file:
        lc.fill(1)
    else:
        with rasterio.open(lc_file, "r") as ds:
            lc[:, :] = ds.read(1, window=win, out_dtype=lc.dtype)
        if lc.dtype != np.uint8:
            lc[:] = lc.astype(np.uint8, copy=False)

    return vi, qa, lc


# def open_image_data_batched(
#     x_map: int,
#     y_map: int,
#     x: int,
#     y: int,
#     data_files: list[str],
#     qa_files: list[str],
#     lc_file: str | None,
#     data_type: str,
#     p_a,
#     layer: int,
#     batch_size: int = 32,
#     s3_opts: dict | None = None,  # kept for API compatibility, but NOT used
# ):
#     """
#     Read VI, QA, and LC blocks by opening datasets in small batches.

#     IMPORTANT:
#     - Do NOT use rasterio.Env(AWS_...) in this environment (blocked).
#     - For S3/S3-compatible, pass presigned HTTPS URLs in data_files/qa_files/lc_file.
#     """

#     z = len(data_files)
#     if qa_files and len(qa_files) != z:
#         raise ValueError(f"qa_files length ({len(qa_files)}) must match data_files length ({z})")

#     vi = np.empty((y, x, z), order="F", dtype=data_type)
#     qa = np.empty((y, x, z), order="F", dtype=data_type)
#     lc = np.empty((y, x), order="F", dtype=np.uint8)

#     win = Window(x_map, y_map, x, y)
#     def _read_stack(paths: list[str], out_arr: np.ndarray, band: int):
#         for j0 in range(0, z, batch_size):
#             j1 = min(z, j0 + batch_size)
#             dss = [rasterio.open(p, "r") for p in paths[j0:j1]]
#             try:
#                 for k, ds in enumerate(dss):
#                     ds.read(band, window=win, out=out_arr[:, :, j0 + k])
#             finally:
#                 for ds in dss:
#                     try:
#                         ds.close()
#                     except Exception:
#                         pass

#     # 1) VI
#     _read_stack(data_files, vi, band=layer)

#     # 2) QA
#     if not qa_files:
#         qa.fill(1)
#     else:
#         # QA is usually band 1; change if your QA files differ
#         _read_stack(qa_files, qa, band=1)

#     # 3) LC
#     if not lc_file:
#         lc.fill(1)
#     else:
#         with rasterio.open(lc_file, "r") as ds:
#             ds.read(1, window=win, out=lc)
#         if lc.dtype != np.uint8:
#             lc[:] = lc.astype(np.uint8, copy=False)

#     return vi, qa, lc

