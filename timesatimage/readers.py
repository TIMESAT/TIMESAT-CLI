from __future__ import annotations
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


def read_file_lists(data_list: str, qa_list: str) -> Tuple[List[str], List[str]]:
    qlist: List[str] | str = ''
    with open(data_list, 'r') as f:
        flist = f.read().splitlines()
    if qa_list != '':
        with open(qa_list, 'r') as f:
            qlist = f.read().splitlines()
        if len(flist) != len(qlist):
            raise ValueError("No. of Data and QA are not consistent")
    return flist, (qlist if isinstance(qlist, list) else [])


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
    vi = np.ndarray((y, x, z), order='F', dtype=data_type)
    qa = np.ndarray((y, x, z), order='F', dtype=data_type)

    # VI stack
    if para_check > 1 and ray is not None:
        vi_para = np.ndarray((y, x), order='F', dtype=data_type)

        @ray.remote
        def _readimgpara_(yfname, s3=s3):
            if s3 is not None:
                with rasterio.Env(**s3):
                    with rasterio.open(yfname, 'r') as temp:
                        vi_para[:, :] = temp.read(layer, window=Window(x_map, y_map, x, y))
            else:
                with rasterio.open(yfname, 'r') as temp:
                    vi_para[:, :] = temp.read(layer, window=Window(x_map, y_map, x, y))
            return vi_para

        futures = [_readimgpara_.remote(i) for i in yflist]
        vi = np.stack(ray.get(futures), axis=2)
    else:
        for i, yfname in enumerate(yflist):
            if s3 is not None:
                with rasterio.Env(**s3):
                    with rasterio.open(yfname, 'r') as temp:
                        vi[:, :, i] = temp.read(layer, window=Window(x_map, y_map, x, y))
            else:
                with rasterio.open(yfname, 'r') as temp:
                    vi[:, :, i] = temp.read(layer, window=Window(x_map, y_map, x, y))

    # QA stack
    if wflist == '' or wflist == []:
        qa = np.ones((y, x, z))
    else:
        if para_check > 1 and ray is not None:
            qa_para = np.ndarray((y, x), order='F', dtype=data_type)

            @ray.remote
            def _readqapara_(wfname, s3=s3):
                if s3 is not None:
                    with rasterio.Env(**s3):
                        with rasterio.open(wfname, 'r') as temp:
                            qa_para[:, :] = temp.read(layer, window=Window(x_map, y_map, x, y))
                else:
                    with rasterio.open(wfname, 'r') as temp:
                        qa_para[:, :] = temp.read(layer, window=Window(x_map, y_map, x, y))
                return qa_para

            futures = [_readqapara_.remote(i) for i in wflist]
            qa = np.stack(ray.get(futures), axis=2)
        else:
            for i, wfname in enumerate(wflist):
                if s3 is not None:
                    with rasterio.Env(**s3):
                        with rasterio.open(wfname, 'r') as temp2:
                            qa[:, :, i] = temp2.read(1, window=Window(x_map, y_map, x, y))
                else:
                    with rasterio.open(wfname, 'r') as temp2:
                        qa[:, :, i] = temp2.read(1, window=Window(x_map, y_map, x, y))
        qa = assign_qa_weight(p_a, qa)

    # LC
    if lcfile == '':
        lc = np.ones((y, x))
    else:
        if s3 is not None:
            with rasterio.Env(**s3):
                with rasterio.open(lcfile, 'r') as temp3:
                    lc = temp3.read(1, window=Window(x_map, y_map, x, y))
        else:
            with rasterio.open(lcfile, 'r') as temp3:
                lc = temp3.read(1, window=Window(x_map, y_map, x, y))

    return vi, qa, lc
