from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from timesat_cli.config import build_param_array, load_config
from timesat_cli.dateutils import date_with_ignored_day, generate_output_timeseries_dates
from timesat_cli.qa import assign_qa_weight
from timesat_cli.readers import open_image_data, read_file_lists, strip_band_ref


@dataclass
class ScenarioResult:
    name: str
    dates: list[dt.date]
    yfit: np.ndarray
    yfitqa: np.ndarray
    raw_dates: list[dt.date]
    raw_values: np.ndarray
    used_range_mode_args: bool


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _yyyydoy_to_date(value: int) -> dt.date:
    year = int(value) // 1000
    doy = int(value) - year * 1000
    return dt.date(year, 1, 1) + dt.timedelta(days=doy - 1)


def _filter_by_date(
    timevector: np.ndarray,
    flist: list[str],
    qlist: list[str],
    *,
    start: dt.date | None = None,
    end: dt.date,
    target_year: int | None = None,
    target_cutoff: dt.date | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    keep: list[int] = []
    for i, t in enumerate(timevector):
        date = _yyyydoy_to_date(int(t))
        if start is not None and date < start:
            continue
        if date <= end:
            if (
                target_year is not None
                and target_cutoff is not None
                and date.year == target_year
                and date > target_cutoff
            ):
                continue
            keep.append(i)

    if not keep:
        raise ValueError(f"No observations found through {end.isoformat()}.")

    qsub = [qlist[i] for i in keep] if qlist else []
    return timevector[keep], [flist[i] for i in keep], qsub


def _year_bounds(timevector: np.ndarray) -> tuple[int, int, int]:
    years = [int(t) // 1000 for t in timevector]
    yrstart = min(years)
    yrend = max(years)
    return yrend - yrstart + 1, yrstart, yrend


def _run_timesat_pixel(
    cfg_path: Path,
    row: int,
    col: int,
    *,
    scenario_name: str,
    start_date: dt.date | None,
    end_date: dt.date,
    target_observation_year: int | None = None,
    target_observation_cutoff: dt.date | None = None,
    time_sampling: str,
    monthly_days: list[int],
    drop_first_year: bool,
    drop_last_year: bool,
    require_range_mode: bool,
) -> ScenarioResult:
    import timesat

    cfg = load_config(str(cfg_path))
    s = cfg.settings
    timevector_all, flist_all, qlist_all, _yr, _yrstart, _yrend = read_file_lists(
        s.tv_list,
        s.image_file_list,
        s.quality_file_list,
    )
    timevector, flist, qlist = _filter_by_date(
        timevector_all,
        flist_all,
        qlist_all,
        start=start_date,
        end=end_date,
        target_year=target_observation_year,
        target_cutoff=target_observation_cutoff,
    )
    yr, yrstart, _yrend = _year_bounds(timevector)

    with _open_first_raster(flist) as first:
        dtype = first.dtypes[0]
        if row < 0 or col < 0 or row >= first.height or col >= first.width:
            raise ValueError(
                f"Pixel row={row}, col={col} is outside raster bounds. "
                f"Valid row range is 0..{first.height - 1}; "
                f"valid col range is 0..{first.width - 1}. "
                f"Raster size is width={first.width}, height={first.height}."
            )

    vi, qa, lc = open_image_data(
        col,
        row,
        1,
        1,
        flist,
        qlist,
        (s.lc_file if s.lc_file else None),
        dtype,
        s.p_band_id,
    )

    if s.scale != 1 or s.offset != 0:
        vi = vi * s.scale + s.offset
    vi = np.nan_to_num(vi, nan=s.p_ylu[0] - 1)
    qa = assign_qa_weight(s.p_a, qa)

    p_outindex, p_outindex_num = generate_output_timeseries_dates(
        s.p_st_timestep,
        yr,
        yrstart,
        time_sampling=time_sampling,
        time_step_days=1,
        monthly_days=monthly_days,
        drop_first_year=drop_first_year,
        drop_last_year=drop_last_year,
    )

    common_args = (
        yr,
        vi,
        qa,
        timevector,
        lc,
        s.p_nclasses,
        build_param_array(s, "landuse", "uint8"),
        p_outindex,
        s.p_ignoreday,
        s.p_ylu,
        s.p_printflag,
        build_param_array(s, "p_fitmethod", "uint8"),
        build_param_array(s, "p_smooth", "double"),
        s.p_nodata,
        s.p_davailwin,
        s.p_outlier,
        build_param_array(s, "p_nenvi", "uint8"),
        build_param_array(s, "p_wfactnum", "double"),
        build_param_array(s, "p_startmethod", "uint8"),
        build_param_array(s, "p_startcutoff", "double", shape=(2,), fortran_2d=True),
        build_param_array(s, "p_low_percentile", "double"),
        build_param_array(s, "p_fillbase", "uint8"),
        s.p_hrvppformat,
        build_param_array(s, "p_seasonmethod", "uint8"),
        build_param_array(s, "p_seapar", "double"),
    )
    range_mode_args = (
        build_param_array(s, "p_lowrangemode", "int32", fill_value=1),
        build_param_array(s, "p_highrangemode", "int32"),
        build_param_array(s, "p_rangedownweight", "double", fill_value=0.5),
    )
    single_pixel_shape_args = (
        1,
        1,
        1,
        len(timevector),
        p_outindex_num,
    )

    used_range_mode_args = True
    try:
        vpp, vppqa, nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
            *common_args,
            *range_mode_args,
            *single_pixel_shape_args,
        )
    except TypeError as exc:
        if "takes at most 30 arguments" not in str(exc):
            raise
        if require_range_mode:
            raise RuntimeError(
                "This timesat.tsfprocess build does not accept the 3 range-mode "
                "arguments. Install/build the range-mode-enabled timesat package "
                "and run again."
            ) from exc
        used_range_mode_args = False
        vpp, vppqa, nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
            *common_args,
            *single_pixel_shape_args,
        )

    dates = [date_with_ignored_day(yrstart, int(i), s.p_ignoreday) for i in p_outindex]
    raw_dates = [_yyyydoy_to_date(int(t)) for t in timevector]

    return ScenarioResult(
        name=scenario_name,
        dates=dates,
        yfit=np.asarray(yfit[0, 0, :], dtype=float),
        yfitqa=np.asarray(yfitqa[0, 0, :]),
        raw_dates=raw_dates,
        raw_values=np.asarray(vi[0, 0, :], dtype=float),
        used_range_mode_args=used_range_mode_args,
    )


def _open_first_raster(flist: list[str]):
    import rasterio

    return rasterio.open(strip_band_ref(flist[0]), "r")


def _target_series(result: ScenarioResult, target_year: int) -> dict[dt.date, float]:
    return {
        date: float(value)
        for date, value in zip(result.dates, result.yfit)
        if date.year == target_year and np.isfinite(value)
    }


def _metrics(reference: dict[dt.date, float], candidate: dict[dt.date, float]) -> dict[str, float | int | None]:
    dates = sorted(set(reference) & set(candidate))
    if not dates:
        return {"n": 0, "bias": None, "mae": None, "rmse": None, "max_abs": None}

    diff = np.array([candidate[d] - reference[d] for d in dates], dtype=float)
    return {
        "n": len(dates),
        "bias": float(np.mean(diff)),
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "max_abs": float(np.max(np.abs(diff))),
    }


def _write_timeseries_csv(path: Path, target_year: int, results: Iterable[ScenarioResult]) -> None:
    series_by_name = {r.name: _target_series(r, target_year) for r in results}
    all_dates = sorted({d for series in series_by_name.values() for d in series})

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", *series_by_name.keys()])
        for date in all_dates:
            writer.writerow([date.isoformat(), *[series.get(date, "") for series in series_by_name.values()]])


def _full_series(result: ScenarioResult) -> dict[dt.date, float]:
    return {
        date: float(value)
        for date, value in zip(result.dates, result.yfit)
        if np.isfinite(value)
    }


def _write_full_timeseries_csv(path: Path, results: Iterable[ScenarioResult]) -> None:
    series_by_name = {r.name: _full_series(r) for r in results}
    all_dates = sorted({d for series in series_by_name.values() for d in series})

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", *series_by_name.keys()])
        for date in all_dates:
            writer.writerow([date.isoformat(), *[series.get(date, "") for series in series_by_name.values()]])


def _write_metrics_csv(path: Path, target_year: int, reference: ScenarioResult, candidates: Iterable[ScenarioResult]) -> None:
    reference_series = _target_series(reference, target_year)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "n", "bias", "mae", "rmse", "max_abs"])
        for candidate in candidates:
            row = _metrics(reference_series, _target_series(candidate, target_year))
            writer.writerow([candidate.name, row["n"], row["bias"], row["mae"], row["rmse"], row["max_abs"]])


def _write_plot(path: Path, target_year: int, results: Iterable[ScenarioResult]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("matplotlib is not installed; skipping PNG plot.")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 5))

    for result in results:
        dates = []
        values = []
        for date, value in zip(result.dates, result.yfit):
            if date.year == target_year:
                dates.append(date)
                values.append(value)
        ax.plot(dates, values, marker="o", linewidth=1.5, label=result.name)

    ax.set_title(f"Single-pixel TIMESAT yfit comparison for {target_year}")
    ax.set_xlabel("Output date")
    ax.set_ylabel("Fitted value")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_full_plot(path: Path, target_year: int, results: Iterable[ScenarioResult]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("matplotlib is not installed; skipping PNG plot.")
        return

    results = list(results)
    if not results:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(
        len(results),
        1,
        figsize=(14, max(3.0 * len(results), 5.0)),
        sharex=True,
        sharey=False,
    )
    if len(results) == 1:
        axes = [axes]

    for ax, result in zip(axes, results):
        ax.axvspan(
            dt.date(target_year, 1, 1),
            dt.date(target_year, 12, 31),
            color="0.9",
            alpha=0.5,
        )
        ax.scatter(
            result.raw_dates,
            result.raw_values,
            s=7,
            color="0.45",
            alpha=0.35,
            linewidths=0,
            label="retained observations",
        )
        ax.plot(result.dates, result.yfit, color="#1f77b4", linewidth=1.5, label="yfit")
        ax.set_title(result.name)
        ax.set_ylabel("Fitted value")
        ax.set_ylim(-100, 5000)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right")

    axes[-1].set_xlabel("Output date")
    fig.suptitle("Single-pixel TIMESAT yfit by target-year observation cutoff", y=0.995)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_manifest(path: Path, args: argparse.Namespace, results: list[ScenarioResult]) -> None:
    payload = {
        "config": str(args.config),
        "row": args.row,
        "col": args.col,
        "target_year": args.target_year,
        "target_cutoff": args.target_cutoff,
        "future_cutoff": args.future_cutoff,
        "monthly_days": args.monthly_days,
        "scenarios": {
            r.name: {
                "raw_start": r.raw_dates[0].isoformat(),
                "raw_end": r.raw_dates[-1].isoformat(),
                "raw_count": len(r.raw_dates),
                "output_start": r.dates[0].isoformat() if r.dates else None,
                "output_end": r.dates[-1].isoformat() if r.dates else None,
                "output_count": len(r.dates),
                "used_range_mode_args": r.used_range_mode_args,
            }
            for r in results
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one-pixel TIMESAT yfit stability for monthly no-drop prediction "
            "versus legacy -1 output with a future-year buffer."
        )
    )
    parser.add_argument("--config", type=Path, default=Path("HRVPP2_config/VPP/settings_hrvpp2_VPP_v7.json"))
    parser.add_argument("--row", type=int, default=25)
    parser.add_argument("--col", type=int, default=25)
    parser.add_argument("--target-year", type=int, default=2023)
    parser.add_argument(
        "--progressive-target",
        action="store_true",
        help=(
            "Run scenarios that keep all data except target-year observations after "
            "month cutoffs, then plot the full output time series."
        ),
    )
    parser.add_argument(
        "--cutoff-months",
        type=int,
        nargs="+",
        default=[2, 4, 6, 12],
        help="Target-year month cutoffs used with --progressive-target.",
    )
    parser.add_argument(
        "--target-cutoff",
        default=None,
        help="Last observation date for the prediction scenario. Defaults to TARGET_YEAR-02-28.",
    )
    parser.add_argument(
        "--future-cutoff",
        default=None,
        help="Last observation date for the legacy -1 + future-buffer scenario. Defaults to TARGET_YEAR+1-12-31.",
    )
    parser.add_argument(
        "--data-end",
        default=None,
        help="Last observation date used by --progressive-target. Defaults to --future-cutoff, or TARGET_YEAR+1-12-31.",
    )
    parser.add_argument("--monthly-days", type=int, nargs="+", default=[1, 11, 21])
    parser.add_argument(
        "--require-range-mode",
        action="store_true",
        help="Fail unless timesat.tsfprocess accepts the 3 range-mode arguments.",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("experiments/single_pixel_prediction_stability/output"))
    return parser.parse_args()


def _month_end(year: int, month: int) -> dt.date:
    if month < 1 or month > 12:
        raise ValueError("--cutoff-months values must be in [1, 12].")
    if month == 12:
        return dt.date(year, 12, 31)
    return dt.date(year, month + 1, 1) - dt.timedelta(days=1)


def _run_progressive_target(args: argparse.Namespace) -> None:
    full_data_end = (
        _parse_date(args.data_end)
        if args.data_end
        else _parse_date(args.future_cutoff)
        if args.future_cutoff
        else dt.date(args.target_year + 1, 12, 31)
    )
    results: list[ScenarioResult] = []

    for month in args.cutoff_months:
        cutoff = _month_end(args.target_year, month)
        label = "full_year" if month == 12 else f"through_{args.target_year}_{month:02d}"
        result = _run_timesat_pixel(
            args.config,
            args.row,
            args.col,
            scenario_name=label,
            start_date=None,
            end_date=full_data_end,
            target_observation_year=args.target_year,
            target_observation_cutoff=cutoff,
            time_sampling="monthly",
            monthly_days=args.monthly_days,
            drop_first_year=False,
            drop_last_year=False,
            require_range_mode=args.require_range_mode,
        )
        results.append(result)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_full_timeseries_csv(args.out_dir / "progressive_full_timeseries_yfit.csv", results)
    _write_full_plot(args.out_dir / "progressive_full_timeseries_yfit.png", args.target_year, results)
    _write_manifest(args.out_dir / "progressive_manifest.json", args, results)

    print(f"Wrote progressive-target outputs to {args.out_dir}")
    print(f"Full data end: {full_data_end}")
    print(
        "Target-year cutoffs: "
        + ", ".join(_month_end(args.target_year, month).isoformat() for month in args.cutoff_months)
    )
    print(
        "Range-mode arguments used: "
        + ", ".join(f"{r.name}={r.used_range_mode_args}" for r in results)
    )


def main() -> None:
    args = parse_args()
    if args.progressive_target:
        _run_progressive_target(args)
        return

    target_cutoff = _parse_date(args.target_cutoff) if args.target_cutoff else dt.date(args.target_year, 2, 28)
    target_end = dt.date(args.target_year, 12, 31)
    future_cutoff = (
        _parse_date(args.future_cutoff)
        if args.future_cutoff
        else dt.date(args.target_year + 1, 12, 31)
    )

    reference = _run_timesat_pixel(
        args.config,
        args.row,
        args.col,
        scenario_name="reference_full_target_no_future",
        start_date=None,
        end_date=target_end,
        time_sampling="monthly",
        monthly_days=args.monthly_days,
        drop_first_year=False,
        drop_last_year=False,
        require_range_mode=args.require_range_mode,
    )
    prediction_no_future = _run_timesat_pixel(
        args.config,
        args.row,
        args.col,
        scenario_name="prediction_no_future_new_settings",
        start_date=None,
        end_date=target_cutoff,
        time_sampling="monthly",
        monthly_days=args.monthly_days,
        drop_first_year=False,
        drop_last_year=False,
        require_range_mode=args.require_range_mode,
    )
    legacy_with_future = _run_timesat_pixel(
        args.config,
        args.row,
        args.col,
        scenario_name="legacy_minus1_with_future_buffer",
        start_date=None,
        end_date=future_cutoff,
        time_sampling="monthly",
        monthly_days=args.monthly_days,
        drop_first_year=True,
        drop_last_year=True,
        require_range_mode=args.require_range_mode,
    )

    results = [reference, prediction_no_future, legacy_with_future]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_timeseries_csv(args.out_dir / "target_year_yfit.csv", args.target_year, results)
    _write_metrics_csv(
        args.out_dir / "metrics_vs_reference.csv",
        args.target_year,
        reference,
        [prediction_no_future, legacy_with_future],
    )
    _write_plot(args.out_dir / "target_year_yfit.png", args.target_year, results)
    _write_manifest(args.out_dir / "manifest.json", args, results)

    print(f"Wrote outputs to {args.out_dir}")
    print(f"Reference: observations through {target_end}")
    print(f"Prediction/no future: observations through {target_cutoff}")
    print(f"Legacy -1/future buffer: observations through {future_cutoff}")
    print(
        "Range-mode arguments used: "
        + ", ".join(f"{r.name}={r.used_range_mode_args}" for r in results)
    )


if __name__ == "__main__":
    main()
