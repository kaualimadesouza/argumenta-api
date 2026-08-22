"""Guards for the DER decisions autogenerate cannot enforce: audit columns
(decision 6), soft delete with partial uniques (decision 8), enums storing the
DER lowercase values, and the indexes a card asked for by name."""

from sqlalchemy import Enum

import argumenta.adapters.db.models  # noqa: F401  (registers all tables)
from argumenta.adapters.db.base import Base

EXPECTED_TABLES = {
    "users",
    "user_exam_targets",
    "auth_identities",
    "push_devices",
    "themes",
    "stories",
    "characters",
    "chapters",
    "chapter_beats",
    "submissions",
    "evaluations",
    "evaluation_scores",
    "evaluation_annotations",
    "character_reactions",
    "chapter_progress",
    "drafts",
    "daily_activity",
    "telemetry_events",
}


def test_all_der_tables_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_has_audit_and_soft_delete_columns() -> None:
    for table in Base.metadata.tables.values():
        for column_name in ("created_at", "updated_at", "deleted_at"):
            assert column_name in table.c, f"{table.name} is missing {column_name}"
        assert table.c.deleted_at.nullable, f"{table.name}.deleted_at must be nullable"


def test_every_unique_index_is_partial_on_deleted_at() -> None:
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            if not index.unique:
                continue
            where = index.dialect_options["postgresql"]["where"]
            assert where is not None, f"{table.name}.{index.name} is not a partial unique"
            assert "deleted_at IS NULL" in str(where), (
                f"{table.name}.{index.name} does not filter deleted_at IS NULL"
            )


def test_no_plain_unique_constraints_outside_partial_indexes() -> None:
    """Uniqueness must live in partial indexes, never in UNIQUE constraints,
    or soft-deleted rows would block reinsertion."""
    from sqlalchemy import UniqueConstraint

    for table in Base.metadata.tables.values():
        plain = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        assert not plain, f"{table.name} declares UNIQUE constraints: {plain}"


def test_enums_store_der_values_not_python_names() -> None:
    for table in Base.metadata.tables.values():
        for column in table.c:
            if isinstance(column.type, Enum) and column.type.enum_class is not None:
                expected = [member.value for member in column.type.enum_class]
                assert list(column.type.enums) == expected, (
                    f"{table.name}.{column.name} enum stores {column.type.enums}, "
                    f"expected DER values {expected}"
                )


def test_the_telemetry_events_are_indexed_by_user_and_time() -> None:
    """Issue #13 asked for this one by name: the highest volume table in the
    model, read per student and period."""
    by_name = {str(index.name): index for index in Base.metadata.tables["telemetry_events"].indexes}
    index = by_name.get("ix_telemetry_events_user_created")
    assert index is not None, f"missing, found {sorted(by_name)}"
    assert [column.name for column in index.columns] == ["user_id", "created_at"]
