from __future__ import annotations

import datetime
import os
import re
from typing import List, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window

from .qa import assign_qa_weight

try:
    import ray
except Exception:  # optional
    ray = None

__all__ = ["read_file_lists", "open_image_data"]


def _parse_dates_from_name(name: str) -> Tuple[int, int, int]:
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


def _read_time_vector(tlist: str, filepaths: List[str]):
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


def _unique_by_timevector(flist: List[str], qlist: List[str], timevector):
    tv_unique, indices = np.unique(timevector, return_index=True)
    flist2 = [flist[i] for i in indices]
    qlist2 = [qlist[i] for i in indices] if qlist else []
    return tv_unique, flist2, qlist2


def read_file_lists(
    tlist: str, data_list: str, qa_list: str
) -> Tuple[np.ndarray, List[str], List[str], int, int, int]:
    qlist: List[str] | str = ""
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
    yflist: List[str],
    wflist: List[str] | str,
    lcfile: str,
    data_type: str,
    p_a,
    para_check: int,
    layer: int,
    s3: dict | None = None,
):
    """Read VI, QA, and LC blocks as arrays."""
    z = len(yflist)
    vi = np.ndarray((y, x, z), order="F", dtype=data_type)
    qa = np.ndarray((y, x, z), order="F", dtype=data_type)
    lc = np.ndarray((y, x, z), order="F", dtype=np.uint8)

    # VI stack
    if para_check > 1 and ray is not None:
        vi_para = np.ndarray((y, x), order="F", dtype=data_type)

        @ray.remote
        def _readimgpara_(yfname, s3=s3):
            if s3 is not None:
                with rasterio.Env(**s3):
                    with rasterio.open(yfname, "r") as temp:
                        vi_para[:, :] = temp.read(
                            layer, window=Window(x_map, y_map, x, y)
                        )
            else:
                with rasterio.open(yfname, "r") as temp:
                    vi_para[:, :] = temp.read(layer, window=Window(x_map, y_map, x, y))
            return vi_para

        futures = [_readimgpara_.remote(i) for i in yflist]
        vi = np.stack(ray.get(futures), axis=2)
    else:
        for i, yfname in enumerate(yflist):
            if s3 is not None:
                with rasterio.Env(**s3):
                    with rasterio.open(yfname, "r") as temp:
                        vi[:, :, i] = temp.read(
                            layer, window=Window(x_map, y_map, x, y)
                        )
            else:
                with rasterio.open(yfname, "r") as temp:
                    vi[:, :, i] = temp.read(layer, window=Window(x_map, y_map, x, y))

    # QA stack
    if wflist == "" or wflist == []:
        qa = np.ones((y, x, z))
    else:
        if para_check > 1 and ray is not None:
            qa_para = np.ndarray((y, x), order="F", dtype=data_type)

            @ray.remote
            def _readqapara_(wfname, s3=s3):
                if s3 is not None:
                    with rasterio.Env(**s3):
                        with rasterio.open(wfname, "r") as temp:
                            qa_para[:, :] = temp.read(
                                layer, window=Window(x_map, y_map, x, y)
                            )
                else:
                    with rasterio.open(wfname, "r") as temp:
                        qa_para[:, :] = temp.read(
                            layer, window=Window(x_map, y_map, x, y)
                        )
                return qa_para

            futures = [_readqapara_.remote(i) for i in wflist]
            qa = np.stack(ray.get(futures), axis=2)
        else:
            for i, wfname in enumerate(wflist):
                if s3 is not None:
                    with rasterio.Env(**s3):
                        with rasterio.open(wfname, "r") as temp2:
                            qa[:, :, i] = temp2.read(
                                1, window=Window(x_map, y_map, x, y)
                            )
                else:
                    with rasterio.open(wfname, "r") as temp2:
                        qa[:, :, i] = temp2.read(1, window=Window(x_map, y_map, x, y))
        qa = assign_qa_weight(p_a, qa)

    # LC
    if lcfile == "":
        lc = np.ones((y, x))
    else:
        if s3 is not None:
            with rasterio.Env(**s3):
                with rasterio.open(lcfile, "r") as temp3:
                    lc = temp3.read(1, window=Window(x_map, y_map, x, y))
        else:
            with rasterio.open(lcfile, "r") as temp3:
                lc = temp3.read(1, window=Window(x_map, y_map, x, y))

    return vi, qa, lc
