from __future__ import annotations
import os
import math

__all__ = ["create_output_folders", "close_all"]


def create_output_folders(outfolder: str) -> tuple[str, str]:
    vpp_folder = os.path.join(outfolder, "VPP")
    st_folder  = os.path.join(outfolder, "ST")
    os.makedirs(vpp_folder, exist_ok=True)
    os.makedirs(st_folder,  exist_ok=True)
    return st_folder, vpp_folder


def memory_plan(
    dx: int,
    dy: int,
    z: int,
    p_outindex_num: int,
    yr: int,
    max_memory_gb: float,
) -> tuple[int, int]:
    num_layers = (
        2 * z                  # VI + QA
        + 2 * p_outindex_num   # yfit + yfit QA
        + 2 * 13 * 2 * yr      # VPP + VPP QA
        + yr                   # nseason
    )
    
    bytes_per = 8  # float64
    safety = 0.6   # keep 60% margin for overhead
    max_bytes = max_memory_gb * (2 ** 30) * safety

    dy_max = max_bytes / (dx * num_layers * bytes_per * 2) if num_layers > 0 else dy
    y_slice_size = int(min(math.floor(dy_max), dy)) if dy_max > 0 else dy
    y_slice_size = max(1, y_slice_size)
    num_block = int(math.ceil(dy / y_slice_size))
    return y_slice_size, num_block


def close_all(*items):
    """
    Close datasets or other objects that have a .close() method.
    Accepts individual objects and iterables (lists/tuples/etc).
    Ignores None safely.
    """
    for obj in items:
        if obj is None:
            continue

        # If it's an iterable of objects (e.g. list of datasets)
        if isinstance(obj, (list, tuple, set)):
            for x in obj:
                if x is None:
                    continue
                close = getattr(x, "close", None)
                if callable(close):
                    close()
        else:
            # Single object
            close = getattr(obj, "close", None)
            if callable(close):
                close()
