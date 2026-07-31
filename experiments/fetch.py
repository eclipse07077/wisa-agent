from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


def save_checkpoint(
    path: Path,
    completed: set[int],
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(sorted(completed)),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chunk", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output.with_suffix(args.output.suffix + ".parts.json")
    completed = (
        set(json.loads(checkpoint.read_text(encoding="utf-8")))
        if checkpoint.exists()
        else set()
    )
    file_descriptor = os.open(
        args.output,
        os.O_RDWR | os.O_CREAT,
        0o644,
    )
    os.ftruncate(file_descriptor, args.size)
    lock = threading.Lock()
    total_chunks = (args.size + args.chunk - 1) // args.chunk
    ranges = [
        (
            index,
            start,
            min(start + args.chunk, args.size) - 1,
        )
        for index, start in enumerate(range(0, args.size, args.chunk))
        if index not in completed
    ]

    def fetch(item: tuple[int, int, int]) -> tuple[int, int]:
        index, start, end = item
        remote_start = args.offset + start
        remote_end = args.offset + end
        for attempt in range(5):
            try:
                response = requests.get(
                    args.url,
                    headers={
                        "Range": f"bytes={remote_start}-{remote_end}"
                    },
                    stream=True,
                    timeout=(15, 120),
                )
                response.raise_for_status()
                if response.status_code != 206:
                    raise RuntimeError(
                        f"range {index} returned {response.status_code}"
                    )
                offset = start
                for block in response.iter_content(1024 * 1024):
                    if block:
                        os.pwrite(file_descriptor, block, offset)
                        offset += len(block)
                if offset != end + 1:
                    raise RuntimeError(
                        f"range {index} ended at {offset}"
                    )
                with lock:
                    completed.add(index)
                    save_checkpoint(checkpoint, completed)
                    print(
                        len(completed),
                        total_chunks,
                        offset - start,
                        flush=True,
                    )
                return index, offset - start
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError(index)

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(fetch, item) for item in ranges]
            for future in as_completed(futures):
                future.result()
        os.fsync(file_descriptor)
    finally:
        os.close(file_descriptor)
    if len(completed) != total_chunks:
        raise RuntimeError("download is incomplete")
    print(args.output, args.size, flush=True)


if __name__ == "__main__":
    main()
