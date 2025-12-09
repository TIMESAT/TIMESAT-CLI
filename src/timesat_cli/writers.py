from __future__ import annotations

import copy

import numpy as np
import rasterio
from rasterio.windows import Window

__all__ = ["prepare_profiles", "write_layers"]


def prepare_profiles(img_profile, p_nodata: float, scale: float, offset: float):
    img_profile_st = copy.deepcopy(img_profile)
    img_profile_st.update(compress="lzw")
    if scale != 1 or offset != 0:
        img_profile_st.update(dtype=rasterio.float32)

    img_profile_vpp = copy.deepcopy(img_profile)
    img_profile_vpp.update(nodata=p_nodata, dtype=rasterio.float32, compress="lzw")

    img_profile_qa = copy.deepcopy(img_profile)
    img_profile_qa.update(nodata=0, dtype=rasterio.uint8, compress="lzw")

    img_profile_ns = copy.deepcopy(img_profile)
    img_profile_ns.update(nodata=255, dtype=rasterio.uint8, compress="lzw")

    return img_profile_st, img_profile_vpp, img_profile_qa, img_profile_ns


def write_layers(
    datasets: list[rasterio.io.DatasetWriter],
    arrays: np.ndarray,
    window: tuple[int, int, int, int],
) -> None:
    """
    Write a block (window) for each array into the corresponding open dataset.

    datasets : list of open rasterio DatasetWriter objects
    arrays   : np.ndarray with shape (n_layers, y, x) or iterable of 2D arrays
    window   : (x_map, y_map, x, y)
    """
    x_map, y_map, x, y = window
    win = Window(x_map, y_map, x, y)

    for i, arr in enumerate(arrays, 1):
        dst = datasets[i - 1]
        dst.write(arr, window=win, indexes=1)
