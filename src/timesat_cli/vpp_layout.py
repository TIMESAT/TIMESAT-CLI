from __future__ import annotations

import os
from typing import Sequence

import numpy as np

__all__ = [
    "TIMESAT_VPP_NAMES",
    "build_vpp_output_filenames",
    "select_vpp_layers",
]


TIMESAT_VPP_NAMES = [
    "SOSD",
    "SOSV",
    "LSLOPE",
    "EOSD",
    "EOSV",
    "RSLOPE",
    "LENGTH",
    "MINV",
    "MAXD",
    "MAXV",
    "AMPL",
    "TPROD",
    "SPROD",
]

def build_vpp_output_filenames(
    vpp_folder: str,
    yrstart: int,
    yrend: int,
    variable_names: Sequence[str],
    seasons_per_year: int = 2,
) -> tuple[list[str], list[str], list[str]]:
    outvppfn: list[str] = []
    outvppqafn: list[str] = []
    outnsfn: list[str] = []

    for year in range(yrstart, yrend + 1):
        for season in range(1, seasons_per_year + 1):
            for name in variable_names:
                outvppfn.append(
                    os.path.join(vpp_folder, f"TIMESAT_{name}_{year}_season_{season}.tif")
                )
            outvppqafn.append(
                os.path.join(vpp_folder, f"TIMESAT_QA_{year}_season_{season}.tif")
            )
        outnsfn.append(os.path.join(vpp_folder, f"TIMESAT_{year}_numseason.tif"))

    return outvppfn, outvppqafn, outnsfn


def _indices_from_names(src_names: Sequence[str], dst_names: Sequence[str]) -> list[int]:
    index_map = {name: i for i, name in enumerate(src_names)}
    missing = [name for name in dst_names if name not in index_map]
    if missing:
        raise ValueError(f"Missing parameters in source VPP names: {missing}")
    return [index_map[name] for name in dst_names]


def select_vpp_layers(
    vpp_layers: np.ndarray,
    src_names: Sequence[str] = TIMESAT_VPP_NAMES,
    dst_names: Sequence[str] = TIMESAT_VPP_NAMES,
) -> np.ndarray:
    """Select and reorder raw TIMESAT VPP layers for custom outputs."""
    if vpp_layers.ndim != 3:
        raise ValueError(f"vpp_layers must be 3D (n_layers, y, x), got {vpp_layers.shape}")

    src_count = len(src_names)
    if src_count == 0:
        raise ValueError("src_names must not be empty")
    if vpp_layers.shape[0] % src_count != 0:
        raise ValueError(
            f"Layer count {vpp_layers.shape[0]} is not divisible by source param count {src_count}"
        )

    pick_idx = _indices_from_names(src_names, dst_names)
    season_count = vpp_layers.shape[0] // src_count
    selected_layers = []
    for season_i in range(season_count):
        base = season_i * src_count
        for i in pick_idx:
            selected_layers.append(vpp_layers[base + i])

    return np.stack(selected_layers, axis=0)
