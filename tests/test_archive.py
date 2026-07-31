from experiments.archive import Member, next_offset, parse_header


def header(name: str, size: int) -> bytes:
    block = bytearray(512)
    block[: len(name)] = name.encode()
    block[100:108] = b"0000644\0"
    block[108:116] = b"0000000\0"
    block[116:124] = b"0000000\0"
    block[124:136] = f"{size:011o}\0".encode()
    block[136:148] = b"00000000000\0"
    block[148:156] = b"        "
    block[156:157] = b"0"
    block[257:263] = b"ustar\0"
    checksum = sum(block)
    block[148:156] = f"{checksum:06o}\0 ".encode()
    return bytes(block)


def test_parse_header_and_padding():
    member = parse_header(23, 7, 1024, header("day/host.json.gz", 513))
    assert member == Member(
        day=23,
        file_id=7,
        name="day/host.json.gz",
        header_offset=1024,
        data_offset=1536,
        size=513,
    )
    assert next_offset(member) == 2560


def test_zero_header_ends_archive():
    assert parse_header(23, 7, 0, bytes(512)) is None


def test_bad_checksum_is_rejected():
    block = bytearray(header("member", 3))
    block[0] ^= 1
    try:
        parse_header(23, 7, 0, bytes(block))
    except ValueError as error:
        assert str(error) == "tar header checksum mismatch"
    else:
        raise AssertionError("invalid checksum was accepted")
