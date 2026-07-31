from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.request import Request, urlopen


FILES = {
    "optc_h501": "1046BVjpMql1bb5WHr9yQeB6Uq6RpngbM",
    "optc_h201": "1OSZXCQrocFSRN7wkPM02p-BqE2WmgdLD",
}


def request(
    url: str,
    token: str | None,
    byte_offset: int | None = None,
    byte_end: int | None = None,
) -> Request:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if byte_offset is not None:
        suffix = "" if byte_end is None else str(byte_end)
        headers["Range"] = f"bytes={byte_offset}-{suffix}"
    return Request(url, headers=headers)


def metadata(file_id: str, token: str) -> dict[str, str]:
    url = (
        f"https://www.googleapis.com/drive/v3/files/{file_id}"
        "?fields=name,size,md5Checksum"
    )
    with urlopen(request(url, token), timeout=60) as response:
        return json.loads(response.read())


def public_metadata(file_id: str) -> dict[str, str]:
    url = (
        "https://drive.usercontent.google.com/download?"
        f"id={file_id}&export=download&confirm=t"
    )
    with urlopen(request(url, None, 0, 0), timeout=60) as response:
        content_range = response.headers.get("Content-Range", "")
        match = re.fullmatch(r"bytes 0-\d+/(\d+)", content_range)
        if response.status != 206 or match is None:
            raise RuntimeError("public range request was not honored")
        disposition = response.headers.get("Content-Disposition", "")
        name_match = re.search(r'filename="([^"]+)"', disposition)
        return {
            "name": name_match.group(1) if name_match else file_id,
            "size": match.group(1),
        }


def digest(path: Path) -> str:
    value = hashlib.md5()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def download(
    dataset: str,
    output: Path,
    token: str | None,
) -> dict[str, str | int]:
    file_id = FILES[dataset]
    values = metadata(file_id, token) if token else public_metadata(file_id)
    size = int(values["size"])
    expected = values.get("md5Checksum", "").lower()
    output.mkdir(parents=True, exist_ok=True)
    final = output / f"{dataset}.dump"
    partial = output / f"{dataset}.dump.part"
    if final.exists():
        if final.stat().st_size != size:
            raise ValueError("existing dump failed verification")
        if expected and digest(final) != expected:
            raise ValueError("existing dump failed verification")
        return {
            "dataset": dataset,
            "path": str(final),
            "size": size,
            "md5": digest(final),
            "sha256": sha256(final),
        }
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > size:
        raise ValueError("partial dump exceeds remote size")
    required = size - offset
    if shutil.disk_usage(output).free < required + 1024**3:
        raise ValueError("insufficient free space")
    if required:
        if token:
            url = (
                "https://www.googleapis.com/drive/v3/files/"
                f"{file_id}?alt=media"
            )
            ranges = ((offset, None),)
        else:
            url = (
                "https://drive.usercontent.google.com/download?"
                f"id={file_id}&export=download&confirm=t"
            )
            chunk = 64 * 1024 * 1024
            ranges = (
                (start, min(start + chunk, size) - 1)
                for start in range(offset, size, chunk)
            )
        mode = "ab" if offset else "wb"
        with partial.open(mode) as handle:
            for start, end in ranges:
                range_start = start if start or end is not None else None
                with urlopen(
                    request(url, token, range_start, end),
                    timeout=120,
                ) as response:
                    status = getattr(response, "status", response.getcode())
                    if (start or end is not None) and status != 206:
                        raise RuntimeError("resume request was not honored")
                    if end is not None:
                        expected_range = f"bytes {start}-{end}/{size}"
                        if response.headers.get("Content-Range") != expected_range:
                            raise RuntimeError("public range response mismatch")
                    while block := response.read(8 * 1024 * 1024):
                        handle.write(block)
    if partial.stat().st_size != size:
        raise RuntimeError("download size mismatch")
    actual = digest(partial)
    if expected and actual != expected:
        raise RuntimeError("download checksum mismatch")
    partial.replace(final)
    return {
        "dataset": dataset,
        "path": str(final),
        "size": size,
        "md5": actual,
        "sha256": sha256(final),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=tuple(FILES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("WISA_DRIVE_TOKEN")
    print(
        json.dumps(
            download(args.dataset, args.output, token),
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
