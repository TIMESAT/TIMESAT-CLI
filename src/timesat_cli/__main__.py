# src/timesat_cli/__main__.py
import argparse
import os
import sys
import tempfile
from pathlib import Path

def _platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"

def _validate_threads(value: int | None) -> int | None:
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
        raise argparse.ArgumentTypeError(
            f"threads={value} is too large for this machine (cpu_count={cpu})."
        )
    return value

def _set_thread_env(threads: int, plat: str) -> None:
    t = str(int(threads))
    # Fortran/OpenMP（TIMESAT）核心线程数
    os.environ["OMP_NUM_THREADS"] = t
    os.environ.setdefault("OMP_DYNAMIC", "FALSE")

    # 建议：避免 BLAS/NumPy 再开一层线程导致“线程叠加”
    # GUI 的 n_core 通常希望控制的是 TIMESAT(Fortran) 的并行，而不是 BLAS
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    if plat == "windows":
        os.environ.setdefault("KMP_NUM_THREADS", t)

def main() -> None:
    parser = argparse.ArgumentParser(description="Run TIMESAT processing pipeline.")
    parser.add_argument(
        "settings_json",
        help="Path to JSON config file, or '-' to read JSON from stdin."
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=None,
        help="Number of OpenMP threads for TIMESAT. Use 0 to mean 'all CPUs'.",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory (GUI can set this). Used to place temp config/logs.",
    )
    args = parser.parse_args()

    plat = _platform()
    threads = _validate_threads(args.threads)

    # IMPORTANT: set env vars before importing processing / Fortran extension
    if threads is not None:
        _set_thread_env(threads, plat)

    # 1) 允许从 stdin 读 JSON
    if args.settings_json == "-":
        run_dir = Path(args.run_dir) if args.run_dir else Path(tempfile.mkdtemp(prefix="timesat_run_"))
        run_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = run_dir / "settings.json"
        cfg_path.write_text(sys.stdin.read(), encoding="utf-8")
        settings_path = str(cfg_path)
    else:
        settings_path = args.settings_json

    from .processing import run
    run(settings_path)

if __name__ == "__main__":
    main()
