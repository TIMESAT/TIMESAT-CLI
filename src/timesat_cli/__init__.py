"""TIMESAT Runner package.

This package provides a Python interface and CLI wrapper for running TIMESAT
processing pipelines.

Authors:
    Zhanzhang Cai (Lund University)
    Lars Eklundh (Lund University)
    Per Jönsson (Malmö University)

Email:
    zhanzhang.cai@nateko.lu.se
"""

__version__ = "0.1.0"
__all__ = ["run"]

from .processing import run
