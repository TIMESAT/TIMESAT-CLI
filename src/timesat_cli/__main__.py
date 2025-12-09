import os
import json
import argparse

def main():
    parser = argparse.ArgumentParser(description="Run TIMESAT processing pipeline.")
    parser.add_argument("settings_json", help="Path to the JSON configuration file.")
    args = parser.parse_args()

    # read config first (pure Python)
    with open(args.settings_json) as f:
        s = json.load(f)

    # thread control BEFORE heavy imports
    threads = s.get("threads")
    if threads:
        threads = str(int(threads))
        os.environ["OMP_NUM_THREADS"] = threads
        os.environ.setdefault("OPENBLAS_NUM_THREADS", threads)
        os.environ.setdefault("MKL_NUM_THREADS", threads)
        os.environ.setdefault("NUMEXPR_NUM_THREADS", threads)

    # late import of processing (safe)
    from .processing import run
    run(args.settings_json)

if __name__ == "__main__":
    main()
