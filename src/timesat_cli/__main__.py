# src/timesat_cli/__main__.py
import argparse
from .processing import run

def main():
    parser = argparse.ArgumentParser(description="Run TIMESAT processing pipeline.")
    parser.add_argument("settings_json", help="Path to the JSON configuration file.")
    args = parser.parse_args()
    run(args.settings_json)

if __name__ == "__main__":
    main()
