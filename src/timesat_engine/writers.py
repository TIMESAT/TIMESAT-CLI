from __future__ import annotations

import copy

import numpy as np
import rasterio
from rasterio.windows import Window

__all__ = ["prepare_profiles", "write_layers", "build_output_filenames"]


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


def build_output_filenames(st_folder: str, vpp_folder: str, p_outindex, yrstart: int, yrend: int, p_ignoreday: int):
        outyfitfn = []
        outyfitqafn = []
        for i_tv in p_outindex:
            yfitdate = date_with_ignored_day(yrstart, int(i_tv), p_ignoreday)
            outyfitfn.append(os.path.join(st_folder, f"TIMESAT_{yfitdate.strftime('%Y%m%d')}.tif"))
            outyfitqafn.append(os.path.join(st_folder, f"TIMESAT_{yfitdate.strftime('%Y%m%d')}_QA.tif"))

        outvppfn = []
        outvppqafn = []
        outnsfn = []
        for i_yr in range(yrstart, yrend + 1):
            for i_seas in range(2):
                for name in VPP_NAMES:
                    outvppfn.append(os.path.join(vpp_folder, f"TIMESAT_{name}_{i_yr}_season_{i_seas+1}.tif"))
                outvppqafn.append(os.path.join(vpp_folder, f"TIMESAT_QA_{i_yr}_season_{i_seas+1}.tif"))
            outnsfn.append(os.path.join(vpp_folder, f"TIMESAT_{i_yr}_numseason.tif"))
        return outyfitfn, outyfitqafn, outvppfn, outvppqafn, outnsfn


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
