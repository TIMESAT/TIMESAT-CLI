import argparse
import json
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
    os.environ["OMP_NUM_THREADS"] = t
    os.environ.setdefault("OMP_DYNAMIC", "FALSE")

    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    if plat == "windows":
        os.environ.setdefault("KMP_NUM_THREADS", t)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TIMESAT CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run TIMESAT processing pipeline")
    run_parser.add_argument(
        "settings_json",
        help="Path to grouped-schema JSON config file, or '-' to read JSON from stdin.",
    )
    run_parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=None,
        help="Number of OpenMP threads for TIMESAT. Use 0 to mean 'all CPUs'.",
    )
    run_parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional run directory (GUI can set this). Used to place temp config/logs.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate-config",
        help="Migrate legacy settings+classN schema to grouped schema",
    )
    migrate_parser.add_argument("old_json", help="Input legacy JSON path")
    migrate_parser.add_argument("new_json", help="Output grouped JSON path")

    return parser


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _build_parser()
    normalized = argv
    if normalized and normalized[0] not in {"run", "migrate-config"}:
        normalized = ["run", *normalized]
    return parser.parse_args(normalized)


def _run_pipeline(settings_json: str, threads: int | None, run_dir: str | None) -> None:
    plat = _platform()
    validated_threads = _validate_threads(threads)

    if validated_threads is not None:
        _set_thread_env(validated_threads, plat)

    if settings_json == "-":
        target_run_dir = Path(run_dir) if run_dir else Path(tempfile.mkdtemp(prefix="timesat_run_"))
        target_run_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = target_run_dir / "settings.json"
        cfg_path.write_text(sys.stdin.read(), encoding="utf-8")
        settings_path = str(cfg_path)
    else:
        settings_path = settings_json

    from .processing import run

    run(settings_path)


def main() -> None:
    args = _parse_args(sys.argv[1:])

    if args.command == "migrate-config":
        from .config import ConfigError, migrate_legacy_config_file

        try:
            migrate_legacy_config_file(args.old_json, args.new_json)
        except (ConfigError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Config migration failed: {exc}") from exc
        print(f"Migrated config written to {args.new_json}")
        return

    _run_pipeline(
        settings_json=args.settings_json,
        threads=args.threads,
        run_dir=args.run_dir,
    )


if __name__ == "__main__":
    main()
