# TIMESAT4.1.7 README

> This repository provides a Python/Fortran interface to TIMESAT.

> Clean, step‑by‑step instructions to set up, compile, and run TIMESAT. The environment can be created using **conda** and **pip**.

---

## Overview
This repository provides a Python interface (via **NumPy f2py**) to the TIMESAT Fortran routines. You will:

1. Prepare a Python environment (conda or pip).
2. Install timesat from Testpypi.
3. Run the application scripts (e.g., `main.py`) with your settings.

---

## Prerequisites
Before you begin, ensure the following are available:

- **Python**: 3.10 or newer

> Note: Wheels are uploaded to **TestPyPI** for evaluation. Dependencies are resolved from PyPI via an extra index.

Optional/common runtime packages (depending on your scripts): `scipy`, `pandas`, `matplotlib`, `tqdm`, 'rasterio', 'ray'.

---

## 1) Environment Setup

### Using conda
```bash
# Create environment 
conda create -n timesatenv python=3.10 numpy scipy pandas matplotlib tqdm rasterio ray-default -c conda-forge
conda activate timesatenv
```

---

## 2) Install TIMESAT
Install from **TestPyPI**, allowing dependencies to come from PyPI:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple timesat==4.1.7.dev0
```

Verify the install and that the native extension is importable:

```bash
python -c "import timesat, timesat._timesat as _; print('timesat', timesat.__version__, 'OK')"
```

Expected output includes the version and `OK`.

---

## 3) Run the application
Depending on your workflow, you may have helper scripts such as `create_file_list.py` and a main driver `main.py`.

Typical commands:

```bash

# Example: run with a production configuration
python main.py settings.json
```

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

This repository consists of two parts, each under different terms:

- **Python/Fortran interface code** (in `python_interface/`)  
  Licensed under the [Apache License 2.0](./python_interface/LICENSE).  
  You are free to use, modify, and distribute this code under the Apache-2.0 terms.

- **Precompiled wheels (TestPypi download)**  
  **timesat model** is **proprietary and closed-source**.  
  All rights reserved by Zhanzhang Cai(Lund University), Lars Eklundh(Lund University), and Per Jönsson(Malmö University).  
  Usage is subject to [PROPRIETARY-LICENSE.txt](./vendor/PROPRIETARY-LICENSE.txt).  
  Redistribution, modification, or reverse engineering of these libraries is strictly prohibited.

Acknowledgement: Swedish National Space Agency, European Environment Agency, European Space Agency, VITO remote sensing, DHI remote sensing, Cloudflight, Geoville.

Test 
```bash
uv sync --refresh-package timesatimage
```