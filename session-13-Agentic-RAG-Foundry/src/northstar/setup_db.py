"""Create the working database from the generated dataset: python -m northstar.setup_db [--reset]"""
import argparse

from .config import Settings
from .repository import bootstrap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Replace an existing working database")
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        path = bootstrap(settings.dataset_dir / "northstar.sqlite", settings.db_path, overwrite=args.reset)
    except FileExistsError as error:
        raise SystemExit(str(error).replace("pass overwrite", "pass --reset"))
    print(f"Working database ready: {path}")


if __name__ == "__main__":
    main()
