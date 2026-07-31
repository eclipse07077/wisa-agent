from experiments.pg_index import copy_rows, copy_value


def test_copy_value_decodes_postgres_text():
    assert copy_value(r"\N") is None
    assert copy_value(r"a\tb\\c\141") == "a\tb\\ca"


def test_copy_rows_uses_copy_section_only():
    lines = (
        "SET statement_timeout = 0;\n",
        "COPY public.sample (a, b) FROM stdin;\n",
        "one\ttwo\n",
        "three\t\\N\n",
        "\\.\n",
        "ignored\n",
    )
    assert list(copy_rows(lines)) == [
        ["one", "two"],
        ["three", None],
    ]
    assert list(copy_rows(lines, decode=False)) == [
        ["one", "two"],
        ["three", r"\N"],
    ]
