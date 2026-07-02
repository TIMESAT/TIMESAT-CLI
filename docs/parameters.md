# TIMESAT CLI Parameter Reference

This document describes the `timesat-cli` command-line arguments and grouped JSON configuration parameters. The current version only supports grouped JSON: the top-level object must contain `input`, `output`, and `general`; `metadata` is optional.

## Command-Line Arguments

### Run the processing pipeline

```bash
timesat-cli run path/to/settings.json
```

The `run` subcommand can also be omitted:

```bash
timesat-cli path/to/settings.json
```

| Argument | Type | Default | Description |
|---|---:|---:|---|
| `settings_json` | path or `-` | required | Path to a grouped JSON configuration file. Use `-` to read JSON from standard input. |
| `-t`, `--threads` | int | unset | Number of OpenMP threads used by TIMESAT. Use `0` for all CPUs. Must be greater than or equal to 0. |
| `--run-dir` | path | unset | Optional run directory, mainly intended for GUI integrations. When `settings_json` is `-`, this directory is used to store the temporary `settings.json`. |

### Migrate a legacy configuration

```bash
timesat-cli migrate-config old_settings.json new_settings.json
```

| Argument | Type | Description |
|---|---:|---|
| `old_json` | path | Legacy JSON file using the old `settings` + `class1/class2/...` schema. |
| `new_json` | path | Output path for the grouped JSON file. |

## Configuration Structure

```json
{
  "metadata": {},
  "input": {},
  "output": {},
  "general": {
    "classes": []
  }
}
```

`metadata` is not used by the processing code. It can be used to record dataset notes, parameter provenance, version information, or other descriptive metadata. `input`, `output`, and `general` are required.

## input

`input` defines the input file lists, quality layers, land-cover raster, and optional S3 environment.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `s3env` | string | `""` | S3/CloudFerro environment prefix or identifier. When empty, inputs are read as local files. When non-empty, the CLI loads the corresponding environment variables and converts image paths to `/vsis3/` paths. |
| `tv_list` | string | `""` | Path to the time-vector list. Each entry normally corresponds to one input image date or time value. |
| `image_file_list` | string | `""` | Path to the vegetation-index or input-image file list. |
| `quality_file_list` | string | `""` | Path to the quality-flag image file list. Quality values are converted to TIMESAT weights using `general.p_a`. |
| `lc_file` | string | `""` | Land-cover raster path. Pixel values are matched against `general.classes[*].landuse` to select class-specific TIMESAT parameters. |

## output

`output` controls the output directory, time-series sampling, VPP layers, and GeoTIFF writing options.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `outputfolder` | string | `""` | Output root directory. If empty, the program exits with `Nothing to do...`. |
| `outputvariables` | int | `1` | Controls VPP output. `1` writes VPP and VPP QA layers; other values are passed to TIMESAT and affect output behavior. |
| `p_st_timestep` | int | `1` | Backward-compatible output time-step parameter. Non-negative values mean regular day intervals; negative values mean legacy monthly output. Prefer the explicit `time_sampling` fields in new configurations. |
| `time_sampling` | string | `"regular"` | yfit output time-series sampling mode. Allowed values are `regular` and `monthly`. |
| `time_step_days` | int | `1` | Output interval in days when `time_sampling = "regular"`. `1` means daily output. |
| `monthly_days` | int[] | `[1, 11, 21]` | Month days to output when `time_sampling = "monthly"`. Values must be between 1 and 31, must not be duplicated, and are sorted by the loader. |
| `drop_first_year` | bool | `false` | Whether to remove the first year from the output date range. Often used to drop a buffer year. |
| `drop_last_year` | bool | `false` | Whether to remove the last year from the output date range. Often used to drop a buffer year. |
| `p_nodata` | number | `-9999` | Output GeoTIFF nodata value. Also passed to TIMESAT. |
| `p_hrvppformat` | int | `1` | HRVPP-style VPP output switch. When set to `1`, date VPP layers are converted from `YYYYDOY` to DOY values relative to the output layer year, and `TPROD`/`SPROD` are divided by 1000. |
| `vpp_dtype` | string | `"float32"` | GeoTIFF data type for VPP outputs. Allowed values: `uint8`, `uint16`, `int16`, `uint32`, `int32`, `float32`, `float64`. |
| `yfit_prefix` | string | `"TIMESAT"` | Filename prefix for yfit outputs. Files are written as `<yfit_prefix>_<YYYYMMDD>.tif` and `<yfit_prefix>_<YYYYMMDD>_QA.tif`. |
| `vpp_prefix` | string | `"TIMESAT"` | Filename prefix for VPP outputs. Files are written as `<vpp_prefix>_<variable>_<year>_season_<n>.tif`. |
| `vpp_variables` | list | all VPP variables | VPP variables to write. Supports string and object forms; see below. |

### Time Sampling Examples

Daily or fixed-interval output:

```json
{
  "time_sampling": "regular",
  "time_step_days": 1,
  "drop_first_year": false,
  "drop_last_year": false
}
```

Output on the 1st, 11th, and 21st of each month, dropping first and last buffer years:

```json
{
  "time_sampling": "monthly",
  "time_step_days": 1,
  "monthly_days": [1, 11, 21],
  "drop_first_year": true,
  "drop_last_year": true
}
```

Legacy `p_st_timestep = -1` is interpreted as the monthly configuration above.

### vpp_variables

`vpp_variables` controls which VPP layers are written and how they are named in output filenames.

String form:

```json
"vpp_variables": ["SOSD", "EOSD", "TPROD"]
```

Object form:

```json
"vpp_variables": [
  { "source": "SOSD" },
  { "source": "TPROD", "name": "TI_PPI" },
  { "source": "SPROD", "enabled": false }
]
```

| Field | Type | Default | Description |
|---|---:|---:|---|
| `source` | string | required | Source TIMESAT VPP variable name. `id` is also accepted as a compatibility alias. |
| `name` | string | same as `source` | Variable name used in the output filename. |
| `enabled` | bool | `true` | If `false`, the variable is skipped. |

Available `source` names:

| Name | Meaning |
|---|---|
| `SOSD` | Start-of-season date. |
| `SOSV` | Vegetation-index value at start of season. |
| `LSLOPE` | Left-side green-up slope. |
| `EOSD` | End-of-season date. |
| `EOSV` | Vegetation-index value at end of season. |
| `RSLOPE` | Right-side senescence slope. |
| `LENGTH` | Season length. |
| `MINV` | Season baseline or minimum value. |
| `MAXD` | Date of maximum value. |
| `MAXV` | Maximum value in the season. |
| `AMPL` | Amplitude. |
| `TPROD` | Total productivity integral. Divided by 1000 in HRVPP format. |
| `SPROD` | Seasonal productivity integral. Divided by 1000 in HRVPP format. |

## general

`general` defines global TIMESAT parameters, input scaling, quality weights, and land-cover class parameters.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `imwindow` | int[4] | `[0, 0, 0, 0]` | Processing window as `[x_offset, y_offset, width, height]`. If the four values sum to 0, the full image is processed. |
| `p_band_id` | int | `1` | Input raster band number to read. |
| `p_ignoreday` | int | `366` | Ignore-day or year-boundary parameter used when converting output time indices to dates. |
| `p_ylu` | number[2] | `[0.0, 10000.0]` | Valid vegetation-index range as `[lower, upper]`. TIMESAT uses this range for low/high boundary handling. |
| `p_a` | list | `[]` | QA-value-to-weight mapping as `[[qa_value, weight], ...]`. QA rasters are converted to TIMESAT weights using this table. |
| `p_davailwin` | int | `45` | Data-availability window passed to TIMESAT. |
| `p_outlier` | int | `0` | Outlier handling switch or mode passed to TIMESAT. |
| `p_printflag` | int | `0` | TIMESAT print/debug output flag. |
| `max_memory_gb` | number | `10` | Memory budget, in GB, used when planning block sizes. Larger values create larger processing blocks but increase memory pressure. |
| `scale` | number | `1` | Scaling factor applied before TIMESAT processing: `vi = vi * scale + offset`. |
| `offset` | number | `0` | Offset applied before TIMESAT processing. |
| `p_nclasses` | int | `len(classes)` | Number of land-cover classes. Optional; if provided, it must equal `len(classes)`. |
| `classes` | object[] | required | Non-empty list of land-cover class parameter objects. |

## general.classes

Each object in `classes` defines TIMESAT parameters for one land-cover class. `landuse` is the only required class field; omitted class parameters use defaults.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `landuse` | int | required | Land-cover class value. This is matched against pixels in `lc_file`. |
| `p_fitmethod` | int | `2` | TIMESAT fitting method. Common choices include Savitzky-Golay, asymmetric Gaussian, and double logistic methods; numeric codes follow the underlying TIMESAT package. |
| `p_smooth` | number | `1000` | Smoothing or fit-strength parameter. Larger values generally produce smoother fitted curves, depending on fitting method. |
| `p_nenvi` | int | `1` | Envelope iteration or envelope-related parameter passed to TIMESAT. |
| `p_wfactnum` | number | `1` | Weight factor affecting how low-quality observations influence the fit. |
| `p_startmethod` | int | `1` | Start/end-of-season threshold method. |
| `p_startcutoff` | number[2] | `[0.25, 0.15]` | Start and end threshold values, usually interpreted as relative amplitude fractions. Must contain exactly two numbers. |
| `p_low_percentile` | number | `0.0` | Low-percentile parameter used for baseline or low-value estimation. |
| `p_fillbase` | int | `0` | Baseline filling switch or mode. |
| `p_seasonmethod` | int | `1` | Season separation method. |
| `p_seapar` | number | `1` | Season separation parameter. |
| `lowrangemode` | int | `1` | Handling mode for values below `p_ylu[0]`. |
| `highrangemode` | int | `0` | Handling mode for values above `p_ylu[1]`. |
| `rangedownweight` | number | `0.5` | Weight multiplier used when a range mode applies downweighting. |

`lowrangemode` and `highrangemode` support:

| Value | Behavior |
|---:|---|
| `0` | Mark as invalid, set weight to 0, and keep the original `y` value. |
| `1` | Clip to the boundary and keep the original weight. |
| `2` | Clip to the boundary and multiply the weight by `rangedownweight`. |

Compatibility field names with a `p_` prefix are also accepted: `p_lowrangemode`, `p_highrangemode`, and `p_rangedownweight`.

## Minimal Configuration Example

```json
{
  "input": {
    "tv_list": "filelists/time_list.txt",
    "image_file_list": "filelists/image_files.txt",
    "quality_file_list": "filelists/qa_files.txt",
    "lc_file": "landcover.tif"
  },
  "output": {
    "outputfolder": "outputs",
    "time_sampling": "regular",
    "time_step_days": 1,
    "vpp_variables": [
      { "source": "SOSD" },
      { "source": "EOSD" },
      { "source": "TPROD", "name": "TI_PPI" }
    ]
  },
  "general": {
    "p_ylu": [0.0, 4999.0],
    "p_a": [[0, 1], [1, 0], [3, 0.5]],
    "classes": [
      {
        "landuse": 1,
        "p_fitmethod": 2,
        "p_smooth": 3000,
        "p_startcutoff": [0.35, 0.15]
      }
    ]
  }
}
```

## Common Configuration Targets

| Goal | Parameters to check |
|---|---|
| Process only a spatial subset | `general.imwindow` |
| Scale input values before fitting | `general.scale`, `general.offset`, `general.p_ylu` |
| Use HRVPP QFLAG/QFLAG2 weights | `general.p_a` |
| Use different fit parameters by land-cover type | `general.classes[*].landuse` and class-level `p_*` parameters |
| Control yfit output dates | `output.time_sampling`, `output.time_step_days`, `output.monthly_days` |
| Control VPP filenames and variable set | `output.vpp_prefix`, `output.vpp_variables` |
| Control memory usage | `general.max_memory_gb` |
