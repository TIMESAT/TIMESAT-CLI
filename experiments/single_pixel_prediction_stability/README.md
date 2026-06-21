# Single-Pixel Prediction Stability Test

This experiment compares one-pixel TIMESAT yfit output for a target year under
two output-date strategies:

- `prediction_no_future_new_settings`: monthly output with no first/last-year drop
- `legacy_minus1_with_future_buffer`: monthly output with first/last-year drop, matching legacy `p_st_timestep = -1`

It also creates `reference_full_target_no_future`, which uses all observations
through the end of the target year. The two candidate runs are compared against
that reference for the target-year monthly dates.

## Current Local Data

The repository's current `tests/vi_filelist.txt` and `tests/qa_filelist.txt`
cover 2020-2024. That means the local equivalent of a 2025/2026 test is:

- target year: 2023
- future buffer year: 2024
- prediction cutoff: 2023-02-28

Run:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 25 \
  --col 25 \
  --target-year 2023 \
  --target-cutoff 2023-02-28 \
  --future-cutoff 2024-12-31
```

To repeat the VITO-style setup on local data, keep all 2020-2024 observations
but retain only different portions of the target year 2023:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 25 \
  --col 25 \
  --target-year 2023 \
  --future-cutoff 2024-12-31 \
  --progressive-target \
  --cutoff-months 2 4 6 12 \
  --require-range-mode
```

This produces:

- `progressive_full_timeseries_yfit.csv`
- `progressive_full_timeseries_yfit.png`
- `progressive_manifest.json`

To run the same progressive target-year test using only 2020-2023 data:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 25 \
  --col 25 \
  --target-year 2023 \
  --data-end 2023-12-31 \
  --progressive-target \
  --cutoff-months 2 4 6 12 \
  --require-range-mode \
  --out-dir experiments/single_pixel_prediction_stability/output_2020_2023
```

To verify that the installed `timesat` build accepts the three range-mode
arguments (`lowrangemode`, `highrangemode`, `rangedownweight`), add:

```bash
  --require-range-mode
```

With this flag, old 30-argument `timesat.tsfprocess` builds fail immediately
instead of silently falling back.

Outputs are written to:

```text
experiments/single_pixel_prediction_stability/output/
```

The main files are:

- `target_year_yfit.csv`: monthly yfit values for each scenario
- `metrics_vs_reference.csv`: bias, MAE, RMSE, and max absolute difference against the reference
- `target_year_yfit.png`: comparison plot
- `manifest.json`: input/output date ranges and observation counts

## VITO 2025/2026 Test

If 2025 has only two months of observations, there is no empirical full-2025
reference curve. In that case the strongest quantitative test should be run as a
holdout on a year where the full target year is available, such as the local
2023/2024 example above.

Once filelists include enough 2025 observations to build a full-target reference
and also include 2026 data, use the same script with:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 25 \
  --col 25 \
  --target-year 2025 \
  --target-cutoff 2025-02-28 \
  --future-cutoff 2026-12-31
```

For this comparison:

- `prediction_no_future_new_settings` uses observations only through February 2025 and outputs 2025 monthly dates with:
  - `time_sampling = monthly`
  - `monthly_days = [1, 11, 21]`
  - `drop_first_year = false`
  - `drop_last_year = false`
- `legacy_minus1_with_future_buffer` uses observations through 2026 and outputs 2025 because 2025 is no longer the last year.

If the `legacy_minus1_with_future_buffer` curve differs more from the full-target
reference than the no-future curve, that supports the argument that using a
future-year buffer can make the target-year fitting unstable for prediction-style
use cases.
