from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Sequence, Tuple

import numpy as np

from .vpp_layout import TIMESAT_VPP_NAMES


ALLOWED_TOP_LEVEL_KEYS = {"input", "output", "general", "metadata"}
LEGACY_MIGRATION_HINT = "timesat-cli migrate-config <old.json> <new.json>"
LEGACY_CLASS_KEY_PATTERN = re.compile(r"^class\d+$")
ALLOWED_VPP_DTYPES = {
    "uint8",
    "uint16",
    "int16",
    "uint32",
    "int32",
    "float32",
    "float64",
}

# Centralized defaults for grouped schema and migration.
DEFAULT_INPUT = {
    "s3env": "",
    "tv_list": "",
    "image_file_list": "",
    "quality_file_list": "",
    "lc_file": "",
}

DEFAULT_OUTPUT = {
    "outputfolder": "",
    "outputvariables": 1,
    "p_st_timestep": -1,
    "p_nodata": -9999,
    "p_hrvppformat": 1,
    "vpp_dtype": "float32",
    "yfit_prefix": "TIMESAT",
    "vpp_prefix": "TIMESAT",
    "vpp_variables": [{"source": name} for name in TIMESAT_VPP_NAMES],
}

DEFAULT_GENERAL = {
    "imwindow": [0, 0, 0, 0],
    "p_band_id": 1,
    "p_ignoreday": 366,
    "p_ylu": [0.0, 10000.0],
    "p_a": [],
    "p_davailwin": 45,
    "p_outlier": 0,
    "p_printflag": 0,
    "max_memory_gb": 10,
    "scale": 1,
    "offset": 0,
}

DEFAULT_CLASS = {
    "landuse": 1,
    "p_fitmethod": 2,
    "p_smooth": 1000,
    "p_nenvi": 1,
    "p_wfactnum": 1,
    "p_startmethod": 1,
    "p_startcutoff": [0.25, 0.15],
    "p_low_percentile": 0.0,
    "p_fillbase": 0,
    "p_seasonmethod": 1,
    "p_seapar": 1,
}

REQUIRED_CLASS_KEYS = tuple(DEFAULT_CLASS.keys())


@dataclass
class ClassParams:
    landuse: int
    p_fitmethod: int
    p_smooth: float
    p_nenvi: int
    p_wfactnum: float
    p_startmethod: int
    p_startcutoff: Tuple[float, float]
    p_low_percentile: float
    p_fillbase: int
    p_seasonmethod: int
    p_seapar: float


@dataclass
class VPPVariable:
    source: str
    name: str


@dataclass
class Settings:
    s3env: str
    image_file_list: str
    quality_file_list: str
    tv_list: str
    lc_file: str
    outputfolder: str
    imwindow: Sequence[int]

    p_band_id: int
    p_ignoreday: int
    p_ylu: np.ndarray
    p_a: List[List[float]]
    p_st_timestep: int
    p_nodata: float
    p_davailwin: int
    p_outlier: int
    p_printflag: int
    max_memory_gb: float
    scale: float
    offset: float
    p_hrvppformat: int
    vpp_dtype: str
    yfit_prefix: str
    vpp_prefix: str
    p_nclasses: int
    classes: List[ClassParams]
    outputvariables: int
    vpp_variables: List[VPPVariable]


@dataclass
class Config:
    settings: Settings


class ConfigError(ValueError):
    pass


def _as_array(value, dtype=float, fortran=False):
    arr = np.array(value, dtype=dtype)
    if fortran:
        arr = np.asfortranarray(arr)
    return arr


def _require_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in parent:
        raise ConfigError(f"Missing required section '{key}'.")
    value = parent[key]
    if not isinstance(value, dict):
        raise ConfigError(f"Section '{key}' must be an object.")
    return value


def _legacy_error_message() -> str:
    return (
        "Legacy config schema detected. "
        "Only grouped schema is supported: top-level keys must be input/output/general "
        "(optional metadata). "
        f"Migrate with: {LEGACY_MIGRATION_HINT}"
    )


def _validate_grouped_schema_root(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a JSON object.")

    if "settings" in data or any(LEGACY_CLASS_KEY_PATTERN.match(k) for k in data):
        raise ConfigError(_legacy_error_message())

    extra = set(data.keys()) - ALLOWED_TOP_LEVEL_KEYS
    if extra:
        extras = ", ".join(sorted(extra))
        raise ConfigError(
            f"Unsupported top-level key(s): {extras}. "
            "Allowed keys are: input, output, general, metadata."
        )

    for required in ("input", "output", "general"):
        if required not in data:
            raise ConfigError(
                f"Missing required section '{required}'. "
                "Expected grouped schema with input/output/general."
            )


def _get_optional(section: dict[str, Any], key: str, default: Any) -> Any:
    return section.get(key, default)


def _require_key(section: dict[str, Any], key: str, section_name: str) -> Any:
    if key not in section:
        raise ConfigError(f"Missing required key '{section_name}.{key}'.")
    return section[key]


def _as_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"'{path}' must be an integer, got boolean.")
    if not isinstance(value, (int, np.integer)):
        raise ConfigError(f"'{path}' must be an integer.")
    return int(value)


def _as_number(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"'{path}' must be numeric, got boolean.")
    if not isinstance(value, (int, float, np.integer, np.floating)):
        raise ConfigError(f"'{path}' must be numeric.")
    return float(value)


def _as_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"'{path}' must be a string.")
    return value


def _as_vpp_dtype(value: Any, path: str) -> str:
    dtype = _as_string(value, path).strip().lower()
    if dtype not in ALLOWED_VPP_DTYPES:
        allowed = ", ".join(sorted(ALLOWED_VPP_DTYPES))
        raise ConfigError(f"'{path}' must be one of: {allowed}.")
    return dtype


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"'{path}' must be a list.")
    return value


def _parse_vpp_variables(raw: Any) -> list[VPPVariable]:
    if raw is None:
        raw = DEFAULT_OUTPUT["vpp_variables"]

    items = _as_list(raw, "output.vpp_variables")
    parsed: list[VPPVariable] = []
    for i, item in enumerate(items):
        path = f"output.vpp_variables[{i}]"
        if isinstance(item, str):
            source = item.strip()
            if not source:
                raise ConfigError(f"'{path}' must not be empty.")
            parsed.append(VPPVariable(source=source, name=source))
            continue

        if not isinstance(item, dict):
            raise ConfigError(f"'{path}' must be either a string or object.")

        source_raw = item.get("source", item.get("id"))
        if source_raw is None:
            raise ConfigError(f"'{path}.source' is required.")
        source = _as_string(source_raw, f"{path}.source").strip()
        if not source:
            raise ConfigError(f"'{path}.source' must not be empty.")

        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"'{path}.enabled' must be boolean when provided.")
        if not enabled:
            continue

        name_raw = item.get("name", source)
        name = _as_string(name_raw, f"{path}.name").strip()
        if not name:
            name = source

        parsed.append(VPPVariable(source=source, name=name))

    return parsed


def _parse_class_params(class_cfg: dict[str, Any], index: int) -> ClassParams:
    if not isinstance(class_cfg, dict):
        raise ConfigError(f"'general.classes[{index}]' must be an object.")

    missing = [k for k in REQUIRED_CLASS_KEYS if k not in class_cfg]
    if missing:
        joined = ", ".join(missing)
        raise ConfigError(f"'general.classes[{index}]' missing required key(s): {joined}.")

    startcutoff_raw = _as_list(class_cfg["p_startcutoff"], f"general.classes[{index}].p_startcutoff")
    if len(startcutoff_raw) != 2:
        raise ConfigError(f"'general.classes[{index}].p_startcutoff' must have exactly 2 values.")

    return ClassParams(
        landuse=_as_int(class_cfg["landuse"], f"general.classes[{index}].landuse"),
        p_fitmethod=_as_int(class_cfg["p_fitmethod"], f"general.classes[{index}].p_fitmethod"),
        p_smooth=_as_number(class_cfg["p_smooth"], f"general.classes[{index}].p_smooth"),
        p_nenvi=_as_int(class_cfg["p_nenvi"], f"general.classes[{index}].p_nenvi"),
        p_wfactnum=_as_number(class_cfg["p_wfactnum"], f"general.classes[{index}].p_wfactnum"),
        p_startmethod=_as_int(class_cfg["p_startmethod"], f"general.classes[{index}].p_startmethod"),
        p_startcutoff=(
            _as_number(startcutoff_raw[0], f"general.classes[{index}].p_startcutoff[0]"),
            _as_number(startcutoff_raw[1], f"general.classes[{index}].p_startcutoff[1]"),
        ),
        p_low_percentile=_as_number(class_cfg["p_low_percentile"], f"general.classes[{index}].p_low_percentile"),
        p_fillbase=_as_int(class_cfg["p_fillbase"], f"general.classes[{index}].p_fillbase"),
        p_seasonmethod=_as_int(class_cfg["p_seasonmethod"], f"general.classes[{index}].p_seasonmethod"),
        p_seapar=_as_number(class_cfg["p_seapar"], f"general.classes[{index}].p_seapar"),
    )


def load_config(jsfile: str) -> Config:
    with open(jsfile, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_config_data(data)


def load_config_data(data: dict[str, Any]) -> Config:
    _validate_grouped_schema_root(data)

    input_cfg = _require_dict(data, "input")
    output_cfg = _require_dict(data, "output")
    general_cfg = _require_dict(data, "general")

    raw_classes = _require_key(general_cfg, "classes", "general")
    classes_list = _as_list(raw_classes, "general.classes")
    if len(classes_list) == 0:
        raise ConfigError("'general.classes' must be a non-empty list.")

    p_nclasses_raw = general_cfg.get("p_nclasses")
    if p_nclasses_raw is not None:
        p_nclasses = _as_int(p_nclasses_raw, "general.p_nclasses")
        if p_nclasses != len(classes_list):
            raise ConfigError(
                "'general.p_nclasses' must match len(general.classes). "
                f"Got p_nclasses={p_nclasses}, len(classes)={len(classes_list)}."
            )
    else:
        p_nclasses = len(classes_list)

    classes = [_parse_class_params(class_cfg, i) for i, class_cfg in enumerate(classes_list)]

    imwindow = _as_list(_get_optional(general_cfg, "imwindow", DEFAULT_GENERAL["imwindow"]), "general.imwindow")
    if len(imwindow) != 4:
        raise ConfigError("'general.imwindow' must have exactly 4 integers.")
    imwindow = [_as_int(v, f"general.imwindow[{i}]") for i, v in enumerate(imwindow)]

    p_ylu = _as_list(_get_optional(general_cfg, "p_ylu", DEFAULT_GENERAL["p_ylu"]), "general.p_ylu")
    if len(p_ylu) != 2:
        raise ConfigError("'general.p_ylu' must have exactly 2 numeric values.")
    p_ylu = [_as_number(p_ylu[0], "general.p_ylu[0]"), _as_number(p_ylu[1], "general.p_ylu[1]")]

    p_a = _as_list(_get_optional(general_cfg, "p_a", DEFAULT_GENERAL["p_a"]), "general.p_a")

    settings = Settings(
        s3env=_as_string(_get_optional(input_cfg, "s3env", DEFAULT_INPUT["s3env"]), "input.s3env"),
        image_file_list=_as_string(_get_optional(input_cfg, "image_file_list", DEFAULT_INPUT["image_file_list"]), "input.image_file_list"),
        quality_file_list=_as_string(_get_optional(input_cfg, "quality_file_list", DEFAULT_INPUT["quality_file_list"]), "input.quality_file_list"),
        tv_list=_as_string(_get_optional(input_cfg, "tv_list", DEFAULT_INPUT["tv_list"]), "input.tv_list"),
        lc_file=_as_string(_get_optional(input_cfg, "lc_file", DEFAULT_INPUT["lc_file"]), "input.lc_file"),
        outputfolder=_as_string(_get_optional(output_cfg, "outputfolder", DEFAULT_OUTPUT["outputfolder"]), "output.outputfolder"),
        imwindow=imwindow,
        p_band_id=_as_int(_get_optional(general_cfg, "p_band_id", DEFAULT_GENERAL["p_band_id"]), "general.p_band_id"),
        p_ignoreday=_as_int(_get_optional(general_cfg, "p_ignoreday", DEFAULT_GENERAL["p_ignoreday"]), "general.p_ignoreday"),
        p_ylu=_as_array(p_ylu, dtype="double", fortran=True),
        p_a=p_a,
        p_st_timestep=_as_int(_get_optional(output_cfg, "p_st_timestep", DEFAULT_OUTPUT["p_st_timestep"]), "output.p_st_timestep"),
        p_nodata=_as_number(_get_optional(output_cfg, "p_nodata", DEFAULT_OUTPUT["p_nodata"]), "output.p_nodata"),
        p_davailwin=_as_int(_get_optional(general_cfg, "p_davailwin", DEFAULT_GENERAL["p_davailwin"]), "general.p_davailwin"),
        p_outlier=_as_int(_get_optional(general_cfg, "p_outlier", DEFAULT_GENERAL["p_outlier"]), "general.p_outlier"),
        p_printflag=_as_int(_get_optional(general_cfg, "p_printflag", DEFAULT_GENERAL["p_printflag"]), "general.p_printflag"),
        max_memory_gb=_as_number(_get_optional(general_cfg, "max_memory_gb", DEFAULT_GENERAL["max_memory_gb"]), "general.max_memory_gb"),
        scale=_as_number(_get_optional(general_cfg, "scale", DEFAULT_GENERAL["scale"]), "general.scale"),
        offset=_as_number(_get_optional(general_cfg, "offset", DEFAULT_GENERAL["offset"]), "general.offset"),
        p_hrvppformat=_as_int(_get_optional(output_cfg, "p_hrvppformat", DEFAULT_OUTPUT["p_hrvppformat"]), "output.p_hrvppformat"),
        vpp_dtype=_as_vpp_dtype(_get_optional(output_cfg, "vpp_dtype", DEFAULT_OUTPUT["vpp_dtype"]), "output.vpp_dtype"),
        yfit_prefix=_as_string(_get_optional(output_cfg, "yfit_prefix", DEFAULT_OUTPUT["yfit_prefix"]), "output.yfit_prefix"),
        vpp_prefix=_as_string(_get_optional(output_cfg, "vpp_prefix", DEFAULT_OUTPUT["vpp_prefix"]), "output.vpp_prefix"),
        outputvariables=_as_int(_get_optional(output_cfg, "outputvariables", DEFAULT_OUTPUT["outputvariables"]), "output.outputvariables"),
        p_nclasses=p_nclasses,
        classes=classes,
        vpp_variables=_parse_vpp_variables(output_cfg.get("vpp_variables")),
    )

    return Config(settings=settings)


def _unwrap_legacy(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _legacy_get(settings: dict[str, Any], key: str, default: Any) -> Any:
    if key not in settings:
        return default
    return _unwrap_legacy(settings[key])


def _migrate_class_block(class_cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, default in DEFAULT_CLASS.items():
        out[key] = _unwrap_legacy(class_cfg.get(key, default))
    return out


def migrate_legacy_config_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a JSON object.")

    if "settings" not in data:
        raise ConfigError("Input does not look like legacy schema: missing top-level 'settings'.")

    legacy_settings = data["settings"]
    if not isinstance(legacy_settings, dict):
        raise ConfigError("Legacy 'settings' section must be an object.")

    class_items: list[tuple[int, dict[str, Any]]] = []
    for key, value in data.items():
        if LEGACY_CLASS_KEY_PATTERN.match(key):
            idx = int(key[5:])
            if not isinstance(value, dict):
                raise ConfigError(f"Legacy '{key}' must be an object.")
            class_items.append((idx, value))

    class_items.sort(key=lambda x: x[0])

    legacy_nclasses = _legacy_get(legacy_settings, "p_nclasses", None)
    if legacy_nclasses is not None:
        try:
            nclasses = int(legacy_nclasses)
        except Exception as exc:
            raise ConfigError("Legacy settings.p_nclasses must be integer-like.") from exc
    else:
        nclasses = len(class_items)

    if nclasses <= 0:
        nclasses = 1

    class_map = {idx: cfg for idx, cfg in class_items}
    migrated_classes: list[dict[str, Any]] = []
    for i in range(1, nclasses + 1):
        cfg = class_map.get(i, {})
        migrated_classes.append(_migrate_class_block(cfg))

    grouped = {
        "input": {
            "s3env": _legacy_get(legacy_settings, "s3env", DEFAULT_INPUT["s3env"]),
            "tv_list": _legacy_get(legacy_settings, "tv_list", DEFAULT_INPUT["tv_list"]),
            "image_file_list": _legacy_get(legacy_settings, "image_file_list", DEFAULT_INPUT["image_file_list"]),
            "quality_file_list": _legacy_get(legacy_settings, "quality_file_list", DEFAULT_INPUT["quality_file_list"]),
            "lc_file": _legacy_get(legacy_settings, "lc_file", DEFAULT_INPUT["lc_file"]),
        },
        "output": {
            "outputfolder": _legacy_get(legacy_settings, "outputfolder", DEFAULT_OUTPUT["outputfolder"]),
            "outputvariables": _legacy_get(legacy_settings, "outputvariables", DEFAULT_OUTPUT["outputvariables"]),
            "p_st_timestep": _legacy_get(legacy_settings, "p_st_timestep", DEFAULT_OUTPUT["p_st_timestep"]),
            "p_nodata": _legacy_get(legacy_settings, "p_nodata", DEFAULT_OUTPUT["p_nodata"]),
            "p_hrvppformat": _legacy_get(legacy_settings, "p_hrvppformat", DEFAULT_OUTPUT["p_hrvppformat"]),
            "vpp_dtype": DEFAULT_OUTPUT["vpp_dtype"],
            "yfit_prefix": DEFAULT_OUTPUT["yfit_prefix"],
            "vpp_prefix": DEFAULT_OUTPUT["vpp_prefix"],
            "vpp_variables": DEFAULT_OUTPUT["vpp_variables"],
        },
        "general": {
            "imwindow": _legacy_get(legacy_settings, "imwindow", DEFAULT_GENERAL["imwindow"]),
            "p_band_id": _legacy_get(legacy_settings, "p_band_id", DEFAULT_GENERAL["p_band_id"]),
            "p_ignoreday": _legacy_get(legacy_settings, "p_ignoreday", DEFAULT_GENERAL["p_ignoreday"]),
            "p_ylu": _legacy_get(legacy_settings, "p_ylu", DEFAULT_GENERAL["p_ylu"]),
            "p_a": _legacy_get(legacy_settings, "p_a", DEFAULT_GENERAL["p_a"]),
            "p_davailwin": _legacy_get(legacy_settings, "p_davailwin", DEFAULT_GENERAL["p_davailwin"]),
            "p_outlier": _legacy_get(legacy_settings, "p_outlier", DEFAULT_GENERAL["p_outlier"]),
            "p_printflag": _legacy_get(legacy_settings, "p_printflag", DEFAULT_GENERAL["p_printflag"]),
            "max_memory_gb": _legacy_get(legacy_settings, "max_memory_gb", DEFAULT_GENERAL["max_memory_gb"]),
            "scale": _legacy_get(legacy_settings, "scale", DEFAULT_GENERAL["scale"]),
            "offset": _legacy_get(legacy_settings, "offset", DEFAULT_GENERAL["offset"]),
            "p_nclasses": nclasses,
            "classes": migrated_classes,
        },
    }

    if "output_hrvpp2" in legacy_settings:
        output_hrvpp2 = int(_legacy_get(legacy_settings, "output_hrvpp2", 0))
        if output_hrvpp2 == 1:
            grouped["output"]["vpp_variables"] = [
                {"source": "SOSD"},
                {"source": "EOSD"},
                {"source": "MAXD"},
                {"source": "SOSV"},
                {"source": "EOSV"},
                {"source": "MINV"},
                {"source": "MAXV"},
                {"source": "LSLOPE"},
                {"source": "RSLOPE"},
                {"source": "TPROD", "name": "TI_PPI"},
            ]

    return grouped


def migrate_legacy_config_file(old_json: str, new_json: str) -> None:
    with open(old_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    grouped = migrate_legacy_config_data(data)

    new_path = Path(new_json)
    if new_path.parent and not new_path.parent.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)

    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_param_array(
    s,
    attr: str,
    dtype,
    size: int = 255,
    shape: Tuple[int, ...] | None = None,
    fortran_2d: bool = False
):
    """
    Build a parameter array for TIMESAT class settings.

    Parameters
    ----------
    s : object
        Settings container with `classes` iterable.
    attr : str
        Attribute on each class object in `s.classes` (e.g., 'p_smooth').
    dtype : numpy dtype or dtype string (e.g., 'uint8', 'double').
    size : int
        Length of the first dimension (TIMESAT expects 255).
    shape : tuple[int, ...] | None
        Extra trailing shape for per-class vectors (e.g., (2,) for p_startcutoff).
    fortran_2d : bool
        If True and `shape==(2,)`, allocate (size,2) with order='F' to mirror legacy layout.

    Returns
    -------
    np.ndarray
        Filled parameter array.
    """
    if shape is None:
        arr = np.zeros(size, dtype=dtype)
        for i, c in enumerate(s.classes):
            arr[i] = getattr(c, attr)
        return arr

    full_shape = (size, *shape)
    order = 'F' if fortran_2d and len(shape) == 1 and shape[0] > 1 else 'C'
    arr = np.zeros(full_shape, dtype=dtype, order=order)
    for i, c in enumerate(s.classes):
        arr[i, ...] = getattr(c, attr)
    return arr
