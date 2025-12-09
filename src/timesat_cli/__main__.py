# src/timesat_cli/__main__.py

import argparse
from . import execute   # import the public wrapper from __init__.py

def main():
    parser = argparse.ArgumentParser(description="Run TIMESAT processing pipeline.")
    parser.add_argument("settings_json", help="Path to the JSON configuration file.")
    args = parser.parse_args()

    # Call the public API (execute), which:
    # - reads the JSON
    # - sets thread environment variables
    # - imports processing lazily
    # - runs the TIMESAT pipeline
    execute(args.settings_json)

if __name__ == "__main__":
    main()
