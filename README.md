# TIMESAT CLI

`TIMESAT CLI` is a command line interface and workflow manager for the [TIMESAT](https://pypi.org/project/timesat/) package. 
It provides a convenient way to configure and execute TIMESAT processing pipelines directly from the command line or automated scripts. 

---

## Requirements

Before you begin, make sure you have:

- **Miniconda** or **Anaconda** (for environment management)  
  Download: [https://docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html)
- **Python 3.10+**

---

## Installation

`timesat-cli` is available on **PyPI** and can be installed using **pip**.  
Although it is not published on Conda, you can safely install it *inside* a Conda environment.

### Option 1 — Install inside a Conda environment

```bash
conda create -n timesat-cli python=3.12
conda activate timesat-cli
pip install timesat-cli
```

> This approach uses Conda only for environment isolation.  
> The installation itself is handled by pip, which will automatically install `timesat` and all required dependencies.

---

### Option 2 — Direct installation with pip

If you already have Python 3.10+ installed:

```bash
pip install timesat-cli
```

---


## Running the Application

After installation, start the CLI with:

```bash
timesat-cli path/to/settings.json
```

or equivalently:

```bash
python -m timesat_cli path/to/settings.json
```

To migrate a legacy config (`settings` + `class1/class2/...`) to the new grouped schema:

```bash
timesat-cli migrate-config old_settings.json new_settings.json
```

---

## Advanced Usage

If you wish to customize or extend the workflow, you can also run or modify the main script directly:

```bash
python timesat_run.py
```

The file 'timesat_run.py' contains the full example pipeline that invokes core modules from the 'timesat_cli' package, including configuration loading, file management, TIMESAT processing, and output writing.

---

## Configuration Format

`timesat-cli` only supports grouped JSON:

- `input`: `s3env`, `tv_list`, `image_file_list`, `quality_file_list`, `lc_file`
- `output`: `outputfolder`, `outputvariables`, `p_st_timestep`, `p_nodata`, `p_hrvppformat`, `vpp_dtype`, `yfit_prefix`, `vpp_prefix`, `vpp_variables`
- `general`: `imwindow`, `p_band_id`, `p_ignoreday`, `p_ylu`, `p_a`, `p_davailwin`, `p_outlier`, `p_printflag`, `max_memory_gb`, `scale`, `offset`, `classes` (and optional `p_nclasses`)

`vpp_variables` controls which VPP layers are written and how they are named. Each entry supports:

- `source` (required): source TIMESAT variable name, e.g. `SOSD`, `TPROD`
- `name` (optional): output layer name; defaults to `source`
- `enabled` (optional): defaults to `true`

`yfit_prefix` and `vpp_prefix` control the filename prefix independently:

- yfit: `<yfit_prefix>_<YYYYMMDD>.tif` and `<yfit_prefix>_<YYYYMMDD>_QA.tif`
- VPP: `<vpp_prefix>_<Output Name>_<year>_season_<n>.tif`
- VPP QA: `<vpp_prefix>_QA_<year>_season_<n>.tif`

`vpp_dtype` controls the raster data type used for VPP outputs. It is optional and defaults to `float32`.
Supported values: `uint8`, `uint16`, `int16`, `uint32`, `int32`, `float32`, `float64`.

`general.classes` is required and must be a non-empty list.
`general.p_nclasses` is optional; when provided, it must equal `len(general.classes)`.

Example:

```json
{
  "input": {
    "s3env": "",
    "tv_list": "filelists/time_list.txt",
    "image_file_list": "filelists/image_files.txt",
    "quality_file_list": "filelists/qa_files.txt",
    "lc_file": "landcover.tif"
  },
  "output": {
    "outputfolder": "outputs/",
    "outputvariables": 1,
    "p_st_timestep": 1,
    "p_nodata": -9999,
    "p_hrvppformat": 1,
    "vpp_dtype": "float32",
    "yfit_prefix": "TIMESAT",
    "vpp_prefix": "TIMESAT",
    "vpp_variables": [
      { "source": "SOSD" },
      { "source": "TPROD", "name": "TI_PPI" }
    ]
  },
  "general": {
    "imwindow": [0, 0, 0, 0],
    "p_band_id": 1,
    "p_ignoreday": 366,
    "p_ylu": [0.00001, 2],
    "p_a": [],
    "p_davailwin": 45,
    "p_outlier": 0,
    "p_printflag": 0,
    "max_memory_gb": 10,
    "scale": 1,
    "offset": 0,
    "p_nclasses": 1,
    "classes": [
      {
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
        "lowrangemode": 1,
        "highrangemode": 0,
        "rangedownweight": 0.5
      }
    ]
  }
}
```

Range handling modes are class-specific. `lowrangemode` and `highrangemode` use:
`0` invalid (`w = 0`, keep `y`), `1` clip to the boundary and keep `w`, and `2` clip to the boundary and multiply `w` by `rangedownweight`.
If omitted, vegetation-index products use `lowrangemode = 1`, `highrangemode = 0`, and `rangedownweight = 0.5`.

---

## HRVPP Notes — QFLAG2 weights
If you work with HRVPP quality flags (`QFLAG2`), the following weights `w` are commonly applied:

| QFLAG2 value | Weight `w` |
|---:|---:|
| 1     | 1.0 |
| 4097  | 1.0 |
| 8193  | 1.0 |
| 12289 | 1.0 |
| 1025  | 0.5 |
| 9217  | 0.5 |
| 2049  | 0.5 |
| 6145  | 0.5 |
| 3073  | 0.5 |

Grouped-schema example:

```json
"general": {
  "p_a": [
    [1, 1.0],
    [4097, 1.0],
    [8193, 1.0],
    [12289, 1.0],
    [1025, 0.5],
    [9217, 0.5],
    [2049, 0.5],
    [6145, 0.5],
    [3073, 0.5]
  ],
  "classes": [ ... ]
}
```

---

## License

**TIMESAT-CLI** is released under the **MIT License**.

You are free to use, modify, and distribute this software under the terms
of the MIT License.

The MIT License applies **only to the source code and assets provided in
this repository**.

### 📦 Dependency and Usage Notice

TIMESAT-CLI is an open-source command-line interface that depends on the
**TIMESAT core**, which is **proprietary software** and licensed separately.

Use of TIMESAT-CLI does **not** grant any rights to use the TIMESAT core
beyond the terms of the TIMESAT license.

- The TIMESAT core is freely available for **non-commercial scientific
  research, academic teaching, and personal use**.
- **Commercial use of the TIMESAT core requires a separate written agreement
  with the authors.**

Each dependency installed with this software retains its own license
(MIT, BSD, Apache, etc.). Users are responsible for complying with the
license terms of all installed components.

### ⚖️ License Summary

| Component          | License Type | Notes |
|--------------------|--------------|-------|
| TIMESAT-CLI        | MIT License  | Open-source CLI and workflow manager. |
| TIMESAT core       | Proprietary  | Licensed separately; commercial use requires agreement. |
| Other dependencies | Various (MIT/BSD/Apache) | See individual package licenses. |

For full license texts, see the `LICENSE` and `NOTICE` files included
with this repository and installed packages.

---

## Citation

If you use **TIMESAT**, **TIMESAT-CLI** or **TIMESAT-GUI** in your research, please cite the corresponding release on Zenodo:

> Cai, Z., Eklundh, L., & Jönsson, P. (2025). *TIMESAT4:  is a software package for analysing time-series of satellite sensor data* (Version 4.1.x) [Computer software]. Zenodo.   
> [https://doi.org/10.5281/zenodo.17369757](https://doi.org/10.5281/zenodo.17369757)

---

## Acknowledgments
  
- This project acknowledges the Swedish National Space Agency (SNSA), the European Environment Agency (EEA), and the European Space Agency (ESA) for their support and for providing access to satellite data and related resources that made this software possible.

---
