"""Which tables hold a student's data, read from the foreign keys themselves: a
hand written list would rot the first time a card adds a table. This walk from
`users` is what the LGPD purge relies on."""

from dataclasses import dataclass

import argumenta.adapters.db.models  # noqa: F401  (registers every table)
from argumenta.adapters.db.base import Base

CASCADE = "CASCADE"
NULLED = "SET NULL"


@dataclass(frozen=True)
class UserFk:
    """A foreign key that points, directly or through another table, at a user."""

    table: str
    column: str
    parent: str
    on_delete: str


def _user_foreign_keys() -> tuple[UserFk, ...]:
    reached = {"users"}
    found: dict[tuple[str, str], UserFk] = {}
    changed = True
    while changed:
        changed = False
        for table in Base.metadata.sorted_tables:
            for key in table.foreign_keys:
                parent = key.column.table.name
                if parent not in reached:
                    continue
                edge = UserFk(
                    table=table.name,
                    column=key.parent.name,
                    parent=parent,
                    on_delete=(key.ondelete or "").upper(),
                )
                if found.setdefault((edge.table, edge.column), edge) is edge:
                    changed = True
                if edge.on_delete == CASCADE and edge.table not in reached:
                    reached.add(edge.table)
                    changed = True
    return tuple(sorted(found.values(), key=lambda edge: (edge.table, edge.column)))


USER_FOREIGN_KEYS = _user_foreign_keys()

DIRECT_USER_TIES = tuple(
    edge for edge in USER_FOREIGN_KEYS if edge.parent == "users" and edge.on_delete == CASCADE
)
"""The tables the purge counts: one WHERE per table, no joins."""

USER_DATA_TABLES = tuple(
    sorted({edge.table for edge in USER_FOREIGN_KEYS if edge.on_delete == CASCADE})
)
"""Everything that leaves when the user row does, dependents included."""

BLOCKING_FOREIGN_KEYS = tuple(
    edge for edge in USER_FOREIGN_KEYS if edge.on_delete not in (CASCADE, NULLED)
)
"""Edges that would make `DELETE FROM users` fail. A guard in the suite keeps
this empty, so a new table cannot quietly break the erasure."""
