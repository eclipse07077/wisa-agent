from __future__ import annotations

import argparse
import json
from pathlib import Path

from wisa_agent.tc.cdm import build_index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2018)
    parser.add_argument("--month", type=int, default=4)
    parser.add_argument("--start-day", type=int, default=1)
    parser.add_argument("--end-day", type=int, default=15)
    args = parser.parse_args()
    try:
        import orjson

        loader = orjson.loads
    except ImportError:
        loader = json.loads

    def progress(records: int, archive_index: int) -> None:
        print(archive_index, records, flush=True)

    counts = build_index(
        args.archives,
        args.output,
        loader=loader,
        progress=progress,
        year=args.year,
        month=args.month,
        start_day=args.start_day,
        end_day=args.end_day,
    )
    print(json.dumps(counts, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
