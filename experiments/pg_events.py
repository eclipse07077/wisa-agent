from __future__ import annotations

from collections.abc import Iterator

from experiments.optc import day_bounds
from wisa_agent.tc.cdm_agent import ProvenanceEvent
from wisa_agent.tc.relations import normalize_relation


Catalog = dict[str, tuple[str, str]]


def node_catalog(connection) -> Catalog:
    catalog = {}
    with connection.cursor() as cursor:
        for table, kind in (
            ("subject_node_table", "subject"),
            ("file_node_table", "file"),
            ("netflow_node_table", "netflow"),
        ):
            cursor.execute(f"select index_id, node_uuid from {table}")
            while rows := cursor.fetchmany(50000):
                catalog.update(
                    {
                        str(index): (str(uuid).upper(), kind)
                        for index, uuid in rows
                    }
                )
    return catalog


def provenance_event(
    row: tuple,
    catalog: Catalog,
) -> ProvenanceEvent | None:
    timestamp, source_index, target_index, raw_relation = row
    source = catalog.get(str(source_index))
    target = catalog.get(str(target_index))
    if source is None or target is None:
        return None
    relation = normalize_relation(
        str(raw_relation),
        source[1],
        target[1],
    )
    if relation is None:
        return None
    return ProvenanceEvent(
        int(timestamp),
        source[0],
        target[0],
        relation,
        "",
        source[1],
        target[1],
    )


def events(
    connection,
    catalog: Catalog,
    days: tuple[int, ...],
) -> Iterator[ProvenanceEvent]:
    for day in days:
        start, stop = day_bounds(day)
        cursor = connection.cursor(name=f"wisa_events_{day}")
        cursor.itersize = 50000
        cursor.execute(
            "select timestamp_rec, src_index_id, dst_index_id, operation "
            "from event_table "
            "where timestamp_rec >= %s and timestamp_rec < %s "
            "order by timestamp_rec, event_uuid",
            (start, stop),
        )
        try:
            for row in cursor:
                event = provenance_event(row, catalog)
                if event is not None:
                    yield event
        finally:
            cursor.close()
