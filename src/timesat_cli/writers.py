from __future__ import annotations

import copy
import threading

import numpy as np
import rasterio
from rasterio.windows import Window

__all__ = ["prepare_profiles", "write_layers", "write_layers_paths"]


def prepare_profiles(img_profile, p_nodata: float, scale: float, offset: float, vpp_dtype: str = "float32"):
    img_profile_st = copy.deepcopy(img_profile)
    img_profile_st.update(nodata=p_nodata, compress="lzw", count=1)
    if scale != 1 or offset != 0:
        img_profile_st.update(dtype=rasterio.float32)

    img_profile_vpp = copy.deepcopy(img_profile)
    img_profile_vpp.update(nodata=p_nodata, dtype=vpp_dtype, compress="lzw", count=1)

    img_profile_qa = copy.deepcopy(img_profile)
    img_profile_qa.update(nodata=0, dtype=rasterio.uint8, compress="lzw", count=1)

    return img_profile_st, img_profile_vpp, img_profile_qa


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


_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _get_path_lock(path: str) -> threading.Lock:
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[path] = lock
        return lock


def write_layers_paths(
    paths: list[str],
    arrays: np.ndarray,
    window: tuple[int, int, int, int],
) -> None:
    """
    Write a block (window) for each array into the corresponding raster path.
    Each write opens the dataset (r+), writes, and closes immediately.
    """
    if len(paths) != len(arrays):
        raise ValueError(f"paths/arrays length mismatch: {len(paths)} != {len(arrays)}")

    x_map, y_map, x, y = window
    win = Window(x_map, y_map, x, y)

    for idx, arr in enumerate(arrays):
        if arr.ndim != 2:
            raise ValueError(f"array at index {idx} must be 2D, got shape {arr.shape}")
        if arr.shape != (y, x):
            raise ValueError(
                f"array at index {idx} has shape {arr.shape}, expected ({y}, {x})"
            )
        path = paths[idx]
        lock = _get_path_lock(path)
        with lock:
            with rasterio.open(path, "r+") as dst:
                dst.write(arr, 1, window=win)
