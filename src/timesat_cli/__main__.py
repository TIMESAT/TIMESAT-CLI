# src/timesat_cli/__main__.py
# Windows: set PYTHONPATH=src
# Windows: python -m timesat_cli -t 12

import argparse
import os
import sys


def _platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def _validate_threads(value: int | None) -> int | None:
    """
    None  -> not provided (do not override config)
    >0    -> use exactly that
    0     -> treat as "use all logical CPUs" (optional behavior)
    """
    if value is None:
        return None

    if not isinstance(value, int):
        raise argparse.ArgumentTypeError("threads must be an integer")

    if value < 0:
        raise argparse.ArgumentTypeError("threads must be >= 0")

    cpu = os.cpu_count() or 1

    if value == 0:
        return cpu

    if value > cpu * 4:
        # protect against accidental huge numbers; adjust policy if you prefer
        raise argparse.ArgumentTypeError(
            f"threads={value} is too large for this machine (cpu_count={cpu})."
        )

    return value


def _set_thread_env(threads: int, plat: str) -> None:
    """
    Set environment variables BEFORE importing Fortran / NumPy / MKL code.
    Uses slightly different defaults by platform.
    """
    t = str(int(threads))

    # Always safe / common:
    os.environ["OMP_NUM_THREADS"] = t
    os.environ.setdefault("OPENBLAS_NUM_THREADS", t)
    os.environ.setdefault("MKL_NUM_THREADS", t)
    os.environ.setdefault("NUMEXPR_NUM_THREADS", t)

    # Intel OpenMP runtime knobs (most relevant on Windows; harmless elsewhere)
    if plat == "windows":
        os.environ.setdefault("KMP_NUM_THREADS", t)
        os.environ.setdefault("OMP_DYNAMIC", "FALSE")  # avoid auto-reducing threads

        # Optional: if you see odd scheduling/perf, you can try enabling one:
        # os.environ.setdefault("KMP_AFFINITY", "granularity=fine,compact,1,0")
        # os.environ.setdefault("KMP_BLOCKTIME", "0")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TIMESAT processing pipeline.")
    parser.add_argument("settings_json", help="Path to the JSON configuration file.")
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=None,
        help="Number of threads. Use 0 to mean 'all CPUs'.",
    )
    args = parser.parse_args()

    plat = _platform()
    threads = _validate_threads(args.threads)

    # IMPORTANT: set env vars before importing processing / Fortran extension
    if threads is not None:
        _set_thread_env(threads, plat)

    from .processing import run
    run(args.settings_json)


if __name__ == "__main__":
    main()
