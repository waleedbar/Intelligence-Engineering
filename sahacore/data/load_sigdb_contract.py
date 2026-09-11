"""Seeds the SIGDB governance tables from sigdb_contract.json.
Requires sql/046_sigdb_contract.sql to already be applied.

    python -m sahacore.data.load_sigdb_contract

The contract row is written first: every other table here is meaningful only
under a stated contract version, and loading the decisions without recording
which contract locked them would store an obligation with no provenance.
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "sigdb_contract.json"

# The README labels, as transcribed, and the column each becomes.
_CONTRACT_COLUMNS = {
    "Contract version": "contract_version",
    "Source authority": "source_authority",
    "As of": "as_of",
    "Public projection": "public_projection",
    "Server state": "server_state",
    "API posture": "api_posture",
    "Clinical status": "clinical_status",
}

# json key -> (table, columns). Order matters only in that the contract row
# goes first; these five reference nothing.
_TABLES = [
    ("state_blocks", "sigdb_state_block",
     ["block_id", "source_row", "block_name", "start_index", "end_index",
      "state_count", "rb_partition", "api_exposure", "source_sheet", "notes"]),
    ("firewall_controls", "sigdb_firewall_control",
     ["control_id", "source_row", "control_class", "rule", "severity", "test",
      "source", "implementation_owner", "status"]),
    ("gaps", "sigdb_gap",
     ["finding_id", "source_row", "product", "severity", "topic", "finding",
      "evidence", "decision", "release_gate", "source_file", "status"]),
    ("qa_gates", "sigdb_qa_gate",
     ["qa_id", "source_row", "severity", "rule", "expected",
      "actual_or_formula", "excel_formula", "status_formula", "source",
      "status"]),
    ("decisions", "sigdb_decision",
     ["decision_id", "source_row", "topic", "finding", "canonical_decision",
      "rationale", "owner", "status", "effective_release"]),
]


def _upsert(cur, table: str, columns: list[str], rows: list[dict]) -> None:
    key = columns[0]
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
    for row in rows:
        # `expected` and `actual_or_formula` arrive as numbers on the gates
        # whose value is a count. The column is TEXT on purpose -- see the
        # migration -- so they are rendered rather than coerced away.
        values = {c: (str(row[c]) if c in ("expected", "actual_or_formula")
                                     and row[c] is not None else row[c])
                  for c in columns}
        cur.execute(
            f"""
            INSERT INTO engine_internal.{table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            values,
        )


def load_sigdb_contract() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}

    conn = get_connection()
    with conn.cursor() as cur:
        contract = {column: data["contract"][label]
                    for label, column in _CONTRACT_COLUMNS.items()}
        cur.execute(
            """
            INSERT INTO engine_internal.sigdb_contract
                (contract_version, source_authority, as_of, public_projection,
                 server_state, api_posture, clinical_status)
            VALUES (%(contract_version)s, %(source_authority)s, %(as_of)s,
                    %(public_projection)s, %(server_state)s, %(api_posture)s,
                    %(clinical_status)s)
            ON CONFLICT (contract_version) DO UPDATE SET
                source_authority = EXCLUDED.source_authority,
                as_of = EXCLUDED.as_of,
                public_projection = EXCLUDED.public_projection,
                server_state = EXCLUDED.server_state,
                api_posture = EXCLUDED.api_posture,
                clinical_status = EXCLUDED.clinical_status
            """,
            contract,
        )
        counts["sigdb_contract"] = 1

        for key, table, columns in _TABLES:
            _upsert(cur, table, columns, data[key])
            counts[table] = len(data[key])

    conn.commit()
    conn.close()
    return counts


if __name__ == "__main__":
    counts = load_sigdb_contract()
    for table, n in counts.items():
        print(f"loaded {n} rows into engine_internal.{table}")
