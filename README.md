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

`timesat-cli` is available on **PyPI** and can be installed using **pip** or **uv**.  
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

### Option 2 — Install via uv (recommended for pure Python environments)

[`uv`](https://github.com/astral-sh/uv) is a modern, high-performance alternative to pip and venv.

1. Install `uv`:

   ```bash
   pip install uv
   # or
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create a virtual environment and install the package:

   ```bash
   uv venv .venv
   source .venv/bin/activate
   uv pip install timesat-cli
   ```

> `uv` provides faster dependency resolution and caching.  
> It will automatically install `timesat` and related dependencies.

---

### Option 3 — Direct installation with pip

If you already have Python 3.10+ installed:

```bash
pip install timesat-cli
```

---


## Running the Application

After installation, start the GUI with:

```bash
timesat-cli path/to/settings.json
```

or equivalently:

```bash
python -m timesat_cli path/to/settings.json
```

---

## Advanced Usage

If you wish to customize or extend the workflow, you can also run or modify the main script directly:

```bash
python timesat_run.py
```

The file 'timesat_run.py' contains the full example pipeline that invokes core modules from the 'timesat_cli' package, including configuration loading, file management, TIMESAT processing, and output writing.

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

Example (settings.json):

```python
"p_a": {
  "value": [
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
  "description": "QA weighting rules. Leave empty [] to keep original QA values. Use [qa_value, weight] for exact matches or [min, max, weight] for ranges."
}
```

---

## License

**TIMESAT-CLI** is released under the **GNU General Public License (GPL)**.  
You are free to use, modify, and distribute this software under the terms of the GPL.

The GPL license applies **only to the TIMESAT-CLI source code and assets** provided in this repository.

### 📦 Dependency Licenses

- `timesat` may install additional open-source dependencies (e.g., Flask, pandas, NumPy).  
- Each dependency retains its own license (MIT, BSD, Apache, etc.).  
- Before redistributing or bundling this software, review the license terms of each dependency carefully.

### ⚖️ Summary

| Component        | License Type | Notes |
|------------------|--------------|-------|
| TIMESAT-CLI      | GPL v3       | Open source, modification and redistribution permitted under GPL. |
| TIMESAT          | Proprietary  | All rights reserved. Redistribution and modification prohibited without written consent. |
| Other Dependencies | Various (MIT/BSD/Apache) | Check individual package licenses before redistribution. |

For detailed license information, refer to the license files distributed with each installed package.

---

## Citation

If you use **TIMESAT**, **TIMESAT-CLI** or **TIMESAT-GUI** in your research, please cite the corresponding release on Zenodo:

> Cai, Z., Eklundh, L., & Jönsson, P. (2025). *TIMESAT4:  is a software package for analysing time-series of satellite sensor data* (Version 4.1.x) [Computer software]. Zenodo.   
> [https://doi.org/10.5281/zenodo.17369757](https://doi.org/10.5281/zenodo.17369757)

---

## Acknowledgments

- [TIMESAT](https://www.nateko.lu.se/TIMESAT) — Original analysis framework for satellite time-series data.  
- This project acknowledges the Swedish National Space Agency (SNSA), the European Environment Agency (EEA), and the European Space Agency (ESA) for their support and for providing access to satellite data and related resources that made this software possible.

---

