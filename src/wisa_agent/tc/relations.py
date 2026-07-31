from __future__ import annotations


TRACKED_RELATIONS = frozenset(
    {
        "EVENT_CONNECT",
        "EVENT_EXECUTE",
        "EVENT_OPEN",
        "EVENT_READ",
        "EVENT_RECVFROM",
        "EVENT_RECVMSG",
        "EVENT_SENDMSG",
        "EVENT_SENDTO",
        "EVENT_WRITE",
        "EVENT_CLONE",
    }
)

REVERSED_RELATIONS = frozenset(
    {
        "EVENT_EXECUTE",
        "EVENT_OPEN",
        "EVENT_READ",
        "EVENT_RECVFROM",
        "EVENT_RECVMSG",
    }
)

OPTC_RELATIONS = frozenset(
    {
        "OPEN",
        "READ",
        "CREATE",
        "MESSAGE",
        "MODIFY",
        "START",
        "RENAME",
        "DELETE",
        "TERMINATE",
        "WRITE",
    }
)


def normalize_relation(
    relation: str,
    source_kind: str = "",
    target_kind: str = "",
) -> str | None:
    if relation in TRACKED_RELATIONS:
        return relation
    kinds = frozenset((source_kind, target_kind))
    if relation == "OPEN" and "file" in kinds:
        return "EVENT_OPEN"
    if relation == "READ" and "file" in kinds:
        return "EVENT_READ"
    if relation == "START":
        if "netflow" in kinds:
            return "EVENT_CONNECT"
        if kinds == {"subject"}:
            return "EVENT_EXECUTE"
    if relation == "CREATE":
        if kinds == {"subject"}:
            return "EVENT_CLONE"
        if "netflow" in kinds:
            return "EVENT_CONNECT"
        if "file" in kinds:
            return "EVENT_WRITE"
    if relation == "MESSAGE" and "netflow" in kinds:
        if source_kind == "netflow":
            return "EVENT_RECVMSG"
        if target_kind == "netflow":
            return "EVENT_SENDMSG"
    if relation in {"MODIFY", "RENAME", "DELETE", "WRITE"} and "file" in kinds:
        return "EVENT_WRITE"
    return None
