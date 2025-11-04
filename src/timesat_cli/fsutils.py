from __future__ import annotations
import os
import math
from typing import Tuple

__all__ = ["create_output_folders"]


def create_output_folders(outfolder: str) -> Tuple[str, str]:
    vpp_folder = os.path.join(outfolder, "VPP")
    st_folder  = os.path.join(outfolder, "ST")
    os.makedirs(vpp_folder, exist_ok=True)
    os.makedirs(st_folder,  exist_ok=True)
    return st_folder, vpp_folder


def memory_plan(dx: int, dy: int, z: int, p_outindex_num: int, yr: int, max_memory_gb: float) -> Tuple[int, int]:
    num_layers = p_outindex_num + z * 2 + (13 * 2) * yr
    bytes_per = 4  # float32
    max_bytes = max_memory_gb * (2 ** 30)
    dy_max = max_bytes / (dx * num_layers * bytes_per)
    y_slice_size = int(min(math.floor(dy_max), dy)) if dy_max > 0 else dy
    y_slice_size = max(1, y_slice_size)
    num_block = int(math.ceil(dy / y_slice_size))
    return y_slice_size, num_block