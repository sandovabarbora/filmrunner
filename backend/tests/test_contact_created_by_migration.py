"""FR-220: contacts.created_by is additive, so a deploy can run old code against the new schema and back."""

from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_the_migration_adds_a_nullable_column_on_top_of_the_previous_head() -> None:
    source = next(path for path in VERSIONS.glob("*.py") if "contacts_created_by" in path.name).read_text()
    assert 'down_revision = "d4f7b0c3e5a6"' in source
    assert 'op.add_column("contacts", sa.Column("created_by", sa.String(length=255), nullable=True))' in source
    assert 'op.drop_column("contacts", "created_by")' in source
