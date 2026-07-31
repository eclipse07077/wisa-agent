from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import requests


FILES = {
    19: 713570,
    20: 713571,
    21: 713572,
    22: 713573,
    23: 713574,
    24: 713575,
    25: 713576,
}
HOSTS = ("0201", "0501")


@dataclass(frozen=True)
class Member:
    day: int
    file_id: int
    name: str
    header_offset: int
    data_offset: int
    size: int


def parse_header(day: int, file_id: int, offset: int, block: bytes) -> Member | None:
    if len(block) != 512:
        raise ValueError("tar header must contain 512 bytes")
    if block == bytes(512):
        return None
    stored = int(block[148:156].rstrip(b"\0 ") or b"0", 8)
    checksum = sum(block[:148]) + 8 * 32 + sum(block[156:])
    if stored != checksum:
        raise ValueError("tar header checksum mismatch")
    name = block[:100].split(b"\0", 1)[0].decode("utf-8")
    prefix = block[345:500].split(b"\0", 1)[0].decode("utf-8")
    if prefix:
        name = f"{prefix}/{name}"
    size = int(block[124:136].rstrip(b"\0 ") or b"0", 8)
    return Member(day, file_id, name, offset, offset + 512, size)


def next_offset(member: Member) -> int:
    return member.data_offset + ((member.size + 511) // 512) * 512


def range_bytes(
    session: requests.Session,
    url: str,
    start: int,
    end: int,
) -> bytes:
    expected = f"bytes {start}-{end}/"
    failure: Exception | None = None
    for attempt in range(5):
        try:
            response = session.get(
                url,
                headers={"Range": f"bytes={start}-{end}"},
                timeout=60,
            )
            response.raise_for_status()
            content_range = response.headers.get("Content-Range", "")
            if response.status_code != 206 or not content_range.startswith(expected):
                raise RuntimeError("range response mismatch")
            if len(response.content) != end - start + 1:
                raise RuntimeError("range length mismatch")
            return response.content
        except (requests.RequestException, RuntimeError) as error:
            failure = error
            time.sleep(2**attempt)
    raise RuntimeError("range request failed") from failure


def signed_url(session: requests.Session, file_id: int) -> str:
    response = session.get(
        f"https://entrepot.recherche.data.gouv.fr/api/access/datafile/{file_id}",
        allow_redirects=False,
        timeout=60,
    )
    if response.status_code != 303 or "Location" not in response.headers:
        raise RuntimeError("archive redirect is unavailable")
    return response.headers["Location"]


def scan_day(day: int) -> tuple[Member, ...]:
    session = requests.Session()
    file_id = FILES[day]
    url = signed_url(session, file_id)
    targets = {f"sysclient{host}.json.gz" for host in HOSTS}
    found: dict[str, Member] = {}
    offset = 0
    while len(found) != len(targets):
        block = range_bytes(session, url, offset, offset + 511)
        member = parse_header(day, file_id, offset, block)
        if member is None:
            break
        for target in targets:
            if member.name.endswith(target):
                found[target] = member
        offset = next_offset(member)
    missing = sorted(targets - found.keys())
    if missing:
        raise RuntimeError(f"missing archive members for day {day}: {missing}")
    return tuple(found[target] for target in sorted(found))


def index() -> tuple[Member, ...]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        groups = tuple(pool.map(scan_day, FILES))
    return tuple(
        sorted(
            (member for group in groups for member in group),
            key=lambda value: (value.day, value.name),
        )
    )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def download(member: Member, output: Path) -> dict[str, str | int]:
    output.mkdir(parents=True, exist_ok=True)
    host = member.name.rsplit("sysclient", 1)[1].split(".", 1)[0]
    final = output / f"{member.day}-{host}.json.gz"
    partial = final.with_suffix(final.suffix + ".part")
    if final.exists():
        if final.stat().st_size != member.size:
            raise ValueError("existing member size mismatch")
        return {
            **asdict(member),
            "path": str(final),
            "sha256": digest(final),
        }
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > member.size:
        raise ValueError("partial member exceeds remote size")
    session = requests.Session()
    url = signed_url(session, member.file_id)
    mode = "ab" if offset else "wb"
    with partial.open(mode) as handle:
        while offset < member.size:
            length = min(4 * 1024 * 1024, member.size - offset)
            start = member.data_offset + offset
            end = start + length - 1
            handle.write(range_bytes(session, url, start, end))
            handle.flush()
            offset += length
    if partial.stat().st_size != member.size:
        raise RuntimeError("member size mismatch")
    partial.replace(final)
    return {
        **asdict(member),
        "path": str(final),
        "sha256": digest(final),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.index.exists():
        payload = json.loads(args.index.read_text(encoding="utf-8"))
        if (
            payload.get("dataset") != "corrected_optc"
            or payload.get("source") != "doi:10.57745/UXCWOC"
            or tuple(payload.get("hosts", ())) != HOSTS
        ):
            raise ValueError("archive index identity mismatch")
        members = tuple(
            Member(**member)
            for member in payload["members"]
        )
    else:
        members = index()
        payload = {
            "dataset": "corrected_optc",
            "source": "doi:10.57745/UXCWOC",
            "hosts": HOSTS,
            "members": [asdict(member) for member in members],
        }
    if args.output is not None:
        ordered = sorted(
            members,
            key=lambda member: (
                "sysclient0501.json.gz" not in member.name,
                member.day,
            ),
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            payload["downloads"] = list(
                pool.map(
                    lambda member: download(member, args.output),
                    ordered,
                )
            )
    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
