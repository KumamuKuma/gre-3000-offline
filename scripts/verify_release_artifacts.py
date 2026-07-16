from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def verify_release_artifacts(
    database_path: Path,
    audit_path: Path,
    expected_records: int,
    expected_reviewed: int,
) -> None:
    if not database_path.is_file():
        raise FileNotFoundError(f"Generated database not found: {database_path}")
    if not audit_path.is_file():
        raise FileNotFoundError(f"Audit JSON not found: {audit_path}")

    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro", uri=True
    )
    try:
        integrity_rows = connection.execute("pragma integrity_check").fetchall()
        metadata_row = connection.execute(
            "select value from metadata where key='record_count'"
        ).fetchone()
    finally:
        connection.close()

    if integrity_rows != [("ok",)]:
        raise RuntimeError(f"SQLite integrity check failed: {integrity_rows}")
    if metadata_row is None:
        raise RuntimeError("SQLite metadata.record_count is missing")
    database_count = int(metadata_row[0])

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_count = int(audit["record_count"])
    unresolved_count = len(audit["unresolved_records"])
    reviewed_count = len(audit["reviewed_records"])
    duplicate_count = len(audit["duplicate_headwords"])

    if database_count != audit_count:
        raise RuntimeError(
            "Record-count mismatch: "
            f"database={database_count}, audit={audit_count}"
        )
    if database_count != expected_records:
        raise RuntimeError(
            f"Unexpected record count: expected={expected_records}, actual={database_count}"
        )
    if unresolved_count:
        raise RuntimeError(f"Strict audit has {unresolved_count} unresolved records")
    if reviewed_count != expected_reviewed:
        raise RuntimeError(
            "Unexpected reviewed-record count: "
            f"expected={expected_reviewed}, actual={reviewed_count}"
        )
    if duplicate_count:
        raise RuntimeError(f"Strict audit has {duplicate_count} duplicate headwords")

    print(
        "release_data_check "
        f"record_count={database_count} unresolved={unresolved_count} "
        f"reviewed={reviewed_count} duplicates={duplicate_count} integrity=ok"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the generated vocabulary database against its strict audit JSON."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--expected-reviewed", type=int, required=True)
    arguments = parser.parse_args()
    verify_release_artifacts(
        arguments.database.resolve(),
        arguments.audit.resolve(),
        arguments.expected_records,
        arguments.expected_reviewed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
