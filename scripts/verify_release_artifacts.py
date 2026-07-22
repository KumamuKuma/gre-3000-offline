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
    expected_equivalence_edges: int,
    expected_machine7_words: int,
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
        metadata = dict(
            connection.execute("select key, value from metadata").fetchall()
        )
        equivalence_count = int(
            connection.execute(
                "select count(*) from equivalence_edges"
            ).fetchone()[0]
        )
        machine7_count = int(
            connection.execute(
                "select count(*) from machine7_membership"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    if integrity_rows != [("ok",)]:
        raise RuntimeError(f"SQLite integrity check failed: {integrity_rows}")
    if "record_count" not in metadata:
        raise RuntimeError("SQLite metadata.record_count is missing")
    database_count = int(metadata["record_count"])

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_count = int(audit["record_count"])
    unresolved_count = len(audit["unresolved_records"])
    reviewed_count = len(audit["reviewed_records"])
    duplicate_count = len(audit["duplicate_headwords"])
    reference_sources = audit["reference_sources"]
    audit_equivalence_count = int(
        reference_sources["equivalence"]["edge_count"]
    )
    audit_machine7_count = int(
        reference_sources["machine7"]["matched_count"]
    )

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
    if equivalence_count != expected_equivalence_edges:
        raise RuntimeError(
            "Unexpected equivalence edge count: "
            f"expected={expected_equivalence_edges}, actual={equivalence_count}"
        )
    if machine7_count != expected_machine7_words:
        raise RuntimeError(
            "Unexpected machine 7.0 word count: "
            f"expected={expected_machine7_words}, actual={machine7_count}"
        )
    if int(metadata.get("equivalence_edge_count", "-1")) != equivalence_count:
        raise RuntimeError("SQLite equivalence-edge metadata mismatch")
    if int(metadata.get("machine7_membership_count", "-1")) != machine7_count:
        raise RuntimeError("SQLite machine-7.0 metadata mismatch")
    if audit_equivalence_count != equivalence_count:
        raise RuntimeError("Audit equivalence-edge count mismatch")
    if audit_machine7_count != machine7_count:
        raise RuntimeError("Audit machine-7.0 word count mismatch")

    print(
        "release_data_check "
        f"record_count={database_count} unresolved={unresolved_count} "
        f"reviewed={reviewed_count} duplicates={duplicate_count} "
        f"equivalence_edges={equivalence_count} machine7_words={machine7_count} "
        "integrity=ok"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the generated vocabulary database against its strict audit JSON."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--expected-records", type=int, required=True)
    parser.add_argument("--expected-reviewed", type=int, required=True)
    parser.add_argument("--expected-equivalence-edges", type=int, required=True)
    parser.add_argument("--expected-machine7-words", type=int, required=True)
    arguments = parser.parse_args()
    verify_release_artifacts(
        arguments.database.resolve(),
        arguments.audit.resolve(),
        arguments.expected_records,
        arguments.expected_reviewed,
        arguments.expected_equivalence_edges,
        arguments.expected_machine7_words,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
