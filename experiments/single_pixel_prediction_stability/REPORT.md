# Single-Pixel TIMESAT Prediction Stability Test

## Purpose

This note documents a single-pixel experiment designed to clarify the difference between the legacy HR-VPP output setting used in VITO's test and a prediction-oriented monthly output setting.

The central question is whether a target year with incomplete observations should be handled by adding a future buffer year, or by keeping the target year as the last output year and disabling last-year trimming.

## Terminology

### Legacy HR-VPP Buffer Setting

This refers to the old setting:

```json
"p_st_timestep": -1
```

In the legacy implementation, this single value combines two independent choices:

- Monthly output sampling on days `[1, 11, 21]`
- Removal of the first and last years from the yfit output

In the explicit configuration syntax this corresponds to:

```json
{
  "time_sampling": "monthly",
  "monthly_days": [1, 11, 21],
  "drop_first_year": true,
  "drop_last_year": true
}
```

With input data from `2020-2025`, this setting removes `2020` and `2025` from the yfit output. Therefore, to obtain yfit output for 2025 under the legacy setting, 2026 data must be added so that 2025 is no longer the last year.

### Prediction-Oriented Monthly Setting

This setting keeps the same monthly output dates but does not remove the target year:

```json
{
  "time_sampling": "monthly",
  "monthly_days": [1, 11, 21],
  "drop_first_year": false,
  "drop_last_year": false
}
```

This allows a target year such as 2025 to be output even when only early-season 2025 observations are available. This setting is more appropriate for prediction-style or early-season monitoring tests because it does not require future-year observations merely to make the target year visible in the output.

## Conceptual Difference

The monthly sampling scheme is the same in both settings. The important difference is the buffer-year trimming:

| Setting | Monthly dates | Drops first year | Drops last year | Needs 2026 to output 2025? |
|---|---:|---:|---:|---:|
| Legacy HR-VPP buffer setting | `[1, 11, 21]` | Yes | Yes | Yes |
| Prediction-oriented monthly setting | `[1, 11, 21]` | No | No | No |

Thus, the prediction-oriented setting is not changing the output sampling frequency. It only separates monthly sampling from the buffer-year trimming rule.

## Local Data Used for the Test

The current local test data cover:

```text
2020-2024
```

The target year used for the local test is:

```text
2023
```

The tested pixel is:

```text
row = 500
col = 500
```

The tests use the range-mode-enabled `timesat.tsfprocess` build.

## Progressive Target-Year Tests

To mimic the VITO-style question using the local complete record, we keep the surrounding time series but progressively remove observations from the target year, 2023:

| Scenario | Target-year observations retained |
|---|---|
| `through_2023_02` | January-February 2023 |
| `through_2023_04` | January-April 2023 |
| `through_2023_06` | January-June 2023 |
| `full_year` | Full 2023 |

All scenarios use monthly yfit output on days `[1, 11, 21]`.

## Experiment A: 2020-2024 Data

This test uses the full local data span, including 2024 after the target year.

Output files:

- [`progressive_full_timeseries_yfit.png`](output/progressive_full_timeseries_yfit.png)
- [`progressive_full_timeseries_yfit.csv`](output/progressive_full_timeseries_yfit.csv)
- [`progressive_manifest.json`](output/progressive_manifest.json)

The manifest reports:

| Scenario | Raw start | Raw end | Raw count | Output start | Output end | Output count |
|---|---|---|---:|---|---|---:|
| `through_2023_02` | 2020-01-02 | 2024-12-31 | 905 | 2020-01-01 | 2024-12-21 | 180 |
| `through_2023_04` | 2020-01-02 | 2024-12-31 | 940 | 2020-01-01 | 2024-12-21 | 180 |
| `through_2023_06` | 2020-01-02 | 2024-12-31 | 977 | 2020-01-01 | 2024-12-21 | 180 |
| `full_year` | 2020-01-02 | 2024-12-31 | 1086 | 2020-01-01 | 2024-12-21 | 180 |

Differences against the `full_year` target-year yfit values:

| Scenario | N | Bias | MAE | RMSE | Max absolute difference |
|---|---:|---:|---:|---:|---:|
| `through_2023_02` | 36 | -750.696 | 763.363 | 1168.274 | 2678.061 |
| `through_2023_04` | 36 | -736.161 | 757.769 | 1161.202 | 2676.585 |
| `through_2023_06` | 36 | -295.198 | 301.509 | 469.446 | 1061.033 |

For this pixel, the early-season-only scenarios do not reconstruct the full 2023 seasonal peak. The fitted curve remains much lower than the full-year reference until enough target-year observations are included.

## Experiment B: 2020-2023 Data Only

This test removes 2024 and processes only `2020-2023`.

Output files:

- [`progressive_full_timeseries_yfit.png`](output_2020_2023/progressive_full_timeseries_yfit.png)
- [`progressive_full_timeseries_yfit.csv`](output_2020_2023/progressive_full_timeseries_yfit.csv)
- [`progressive_manifest.json`](output_2020_2023/progressive_manifest.json)

The manifest reports:

| Scenario | Raw start | Raw end | Raw count | Output start | Output end | Output count |
|---|---|---|---:|---|---|---:|
| `through_2023_02` | 2020-01-02 | 2023-02-28 | 687 | 2020-01-01 | 2023-12-21 | 144 |
| `through_2023_04` | 2020-01-02 | 2023-04-29 | 722 | 2020-01-01 | 2023-12-21 | 144 |
| `through_2023_06` | 2020-01-02 | 2023-06-30 | 759 | 2020-01-01 | 2023-12-21 | 144 |
| `full_year` | 2020-01-02 | 2023-12-30 | 868 | 2020-01-01 | 2023-12-21 | 144 |

Differences against the `full_year` target-year yfit values:

| Scenario | N | Bias | MAE | RMSE | Max absolute difference |
|---|---:|---:|---:|---:|---:|
| `through_2023_02` | 36 | 76.339 | 81.160 | 113.309 | 265.088 |
| `through_2023_04` | 36 | 59.228 | 63.931 | 101.480 | 266.306 |
| `through_2023_06` | 36 | 28.010 | 43.994 | 83.175 | 256.625 |

For this pixel, the no-future-year test gives smaller target-year differences than the version that also included 2024. This supports the concern that adding a future year can change the fitted target-year curve, which is undesirable for prediction-oriented evaluation.

## Interpretation

The results show that TIMESAT fitting is sensitive to how the target year is treated at the temporal boundary. Under the legacy HR-VPP buffer setting, the target year is only available if an additional future year is supplied. This makes the target-year output retrospective, because future observations can influence the fitted curve.

For a prediction-oriented test, the target year should remain in the output without requiring future-year data. The prediction-oriented monthly setting preserves the same monthly output dates as the legacy setting, while avoiding automatic last-year removal.

## Suggested Wording for VITO

The legacy `p_st_timestep = -1` setting conflates monthly output sampling with buffer-year trimming. For HR-VPP production this is useful, because the first and last years can be treated as temporal buffers. However, for prediction-oriented experiments the last year is the evaluation year and should not be removed.

Therefore, we use the same monthly output schedule as the legacy setting, `[1, 11, 21]`, but disable first-year and last-year trimming. This allows the target year to be evaluated without adding future-year data. If future-year data are added only to make the target year visible under the legacy setting, the resulting target-year fit is retrospective rather than a strict prediction.

## Reproducible Commands

2020-2024 progressive test:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 500 \
  --col 500 \
  --target-year 2023 \
  --future-cutoff 2024-12-31 \
  --progressive-target \
  --cutoff-months 2 4 6 12 \
  --require-range-mode
```

2020-2023 progressive test:

```bash
python experiments/single_pixel_prediction_stability/run_single_pixel_stability.py \
  --config HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json \
  --row 500 \
  --col 500 \
  --target-year 2023 \
  --data-end 2023-12-31 \
  --progressive-target \
  --cutoff-months 2 4 6 12 \
  --require-range-mode \
  --out-dir experiments/single_pixel_prediction_stability/output_2020_2023
```
