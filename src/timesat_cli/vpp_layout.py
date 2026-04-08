from __future__ import annotations

import os
from typing import Sequence

import numpy as np

__all__ = [
    "TIMESAT_VPP_NAMES",
    "build_vpp_output_filenames",
    "build_vpp_season_years",
    "build_vpp_layer_transform_info",
    "convert_date_vpp_layers_to_layer_doy",
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

_DATE_VPP_NAMES = ("SOSD", "EOSD", "MAXD")
_SCALED_VPP_NAMES = ("TPROD", "SPROD")


def build_vpp_season_years(
    yrstart: int,
    yrend: int,
    seasons_per_year: int = 2,
) -> list[int]:
    """Build the season-year sequence using the same ordering as VPP filenames."""
    if seasons_per_year <= 0:
        raise ValueError("seasons_per_year must be positive")
    if yrend < yrstart:
        raise ValueError("yrend must be >= yrstart")

    season_years: list[int] = []
    for year in range(yrstart, yrend + 1):
        for _season in range(1, seasons_per_year + 1):
            season_years.append(year)
    return season_years


def build_vpp_layer_transform_info(
    yrstart: int,
    yrend: int,
    src_names: Sequence[str] = TIMESAT_VPP_NAMES,
    seasons_per_year: int = 2,
) -> tuple[np.ndarray, list[int], list[int]]:
    """Return precomputed transform info for raw VPP outputs."""
    season_years = build_vpp_season_years(yrstart, yrend, seasons_per_year)
    date_indices = _indices_from_names(src_names, _DATE_VPP_NAMES)
    scaled_indices = _indices_from_names(src_names, _SCALED_VPP_NAMES)
    layer_years = np.repeat(np.asarray(season_years, dtype=np.float64), len(date_indices))
    return layer_years, date_indices, scaled_indices

def build_vpp_output_filenames(
    vpp_folder: str,
    yrstart: int,
    yrend: int,
    variable_names: Sequence[str],
    prefix: str = "TIMESAT",
    seasons_per_year: int = 2,
) -> tuple[list[str], list[str], list[str]]:
    outvppfn: list[str] = []
    outvppqafn: list[str] = []
    outnsfn: list[str] = []

    season_years = build_vpp_season_years(yrstart, yrend, seasons_per_year)
    for season_i, year in enumerate(season_years):
        season = season_i % seasons_per_year + 1
        for name in variable_names:
            outvppfn.append(
                os.path.join(vpp_folder, f"{prefix}_{name}_{year}_season_{season}.tif")
            )
        outvppqafn.append(
            os.path.join(vpp_folder, f"{prefix}_QA_{year}_season_{season}.tif")
        )

    for year in range(yrstart, yrend + 1):
        outnsfn.append(os.path.join(vpp_folder, f"{prefix}_{year}_numseason.tif"))

    return outvppfn, outvppqafn, outnsfn


def convert_date_vpp_layers_to_layer_doy(
    vpp_layers: np.ndarray,
    layer_years: np.ndarray,
    date_indices: Sequence[int],
    scaled_indices: Sequence[int],
    p_nodata: float | None = None,
    src_names: Sequence[str] = TIMESAT_VPP_NAMES,
) -> np.ndarray:
    """
    Convert YYYYDOY-style date layers to DOY values relative to each layer year.

    TIMESAT date outputs encode dates as YYYYDOY. For GeoTIFF VPP layers we store
    these as continuous day-of-year values anchored to the output layer year:
    ``DOY + (layer_year - src_year) * 365``.
    """
    if vpp_layers.ndim != 3:
        raise ValueError(f"vpp_layers must be 3D (n_layers, y, x), got {vpp_layers.shape}")
    src_count = len(src_names)
    if src_count == 0:
        raise ValueError("src_names must not be empty")
    if vpp_layers.shape[0] % src_count != 0:
        raise ValueError(
            f"Layer count {vpp_layers.shape[0]} is not divisible by source param count {src_count}"
        )

    season_count = vpp_layers.shape[0] // src_count
    expected_layer_count = season_count * len(date_indices)
    if len(layer_years) != expected_layer_count:
        raise ValueError(
            f"Date-layer year count {len(layer_years)} does not match expected date-layer count {expected_layer_count}"
        )
    converted = vpp_layers.copy()

    layer_year_idx = 0
    for season_i in range(season_count):
        base = season_i * src_count
        for idx in date_indices:
            layer_year = layer_years[layer_year_idx]
            layer_year_idx += 1
            layer = converted[base + idx]
            finite = np.isfinite(layer)
            if p_nodata is not None:
                finite &= ~np.isclose(layer, p_nodata)
            if not np.any(finite):
                continue

            src_values = layer[finite].astype(np.float64)
            src_year = np.floor(src_values / 1000.0)
            src_doy = src_values - src_year * 1000.0
            valid_yyyydoy = (
                (src_year >= 1000)
                & (src_year <= 9999)
                & (src_doy >= 0)
                & (src_doy <= 367)
            )
            if not np.any(valid_yyyydoy):
                continue

            finite_idx = np.flatnonzero(finite)
            target_idx = finite_idx[valid_yyyydoy]
            layer_flat = layer.reshape(-1)
            layer_flat[target_idx] = (
                src_doy[valid_yyyydoy] + (src_year[valid_yyyydoy] - layer_year) * 365
            )

        for idx in scaled_indices:
            layer = converted[base + idx]
            finite = np.isfinite(layer)
            if p_nodata is not None:
                finite &= ~np.isclose(layer, p_nodata)
            if not np.any(finite):
                continue
            layer[finite] = layer[finite] / 1000.0

    return converted


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
