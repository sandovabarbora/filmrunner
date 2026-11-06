"""FR-220: production imports pypdf, so its pin belongs with the runtime dependencies."""

from pathlib import Path

REQUIREMENTS = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text().splitlines()


def test_pypdf_is_pinned_outside_the_testing_block() -> None:
    testing_starts = REQUIREMENTS.index("# testing")
    assert any(line.startswith("pypdf==") for line in REQUIREMENTS[:testing_starts])
    assert not any(line.startswith("pypdf==") for line in REQUIREMENTS[testing_starts:])


def test_pypdf_is_at_least_the_version_pip_audit_reported_clean() -> None:
    pin = next(line for line in REQUIREMENTS if line.startswith("pypdf=="))
    assert tuple(int(part) for part in pin.split("==")[1].split(".")) >= (6, 21, 4)
