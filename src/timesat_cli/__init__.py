"""
TIMESAT Runner package.

This package provides a Python interface and CLI wrapper for running TIMESAT
processing pipelines.
"""

def execute(jsfile: str) -> None:
    import os
    import json

    # 1. Read JSON
    with open(jsfile, "r") as f:
        cfg = json.load(f)

    # 2. Configure threads
    threads = cfg.get("threads")
    if threads:
        threads = str(int(threads))
        os.environ["OMP_NUM_THREADS"] = threads
        os.environ.setdefault("OPENBLAS_NUM_THREADS", threads)
        os.environ.setdefault("MKL_NUM_THREADS", threads)
        os.environ.setdefault("NUMEXPR_NUM_THREADS", threads)

    # 3. Import processing after setting environment
    from .processing import run 

    # 4. Call it directly
    return run(jsfile)
