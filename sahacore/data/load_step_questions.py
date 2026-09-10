"""Seeds the onboarding questionnaire from step_questions.json.
Requires sql/038_step_questions.sql to already be applied.

    python -m sahacore.data.load_step_questions
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "step_questions.json"

_STEP_COLUMNS = ["step_number", "source_row", "title"]
_QUESTION_COLUMNS = ["source_row", "step_number", "category", "question",
                     "answer_options_text", "is_choice", "variable",
                     "reverse_scored", "required"]
_TARGET_COLUMNS = ["source_row", "target"]
_OPTION_COLUMNS = ["source_row", "ordinal_position", "option"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    keys = {k.strip() for k in key.split(",")}
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in keys)
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """
            if updates else
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO NOTHING
            """,
            {c: row[c] for c in columns},
        )


def load_step_questions() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    questions = data["questions"]

    targets = [{"source_row": q["source_row"], "target": target}
               for q in questions for target in q["targets"]]
    options = [{"source_row": q["source_row"], "ordinal_position": position,
                "option": option}
               for q in questions
               for position, option in enumerate(q["answer_options"], start=1)]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_step_question_step",
                _STEP_COLUMNS, "step_number", data["steps"])
        _upsert(cur, "engine_internal.onboarding_step_question",
                _QUESTION_COLUMNS, "source_row", questions)
        _upsert(cur, "engine_internal.onboarding_step_question_target",
                _TARGET_COLUMNS, "source_row, target", targets)
        _upsert(cur, "engine_internal.onboarding_step_question_option",
                _OPTION_COLUMNS, "source_row, ordinal_position", options)
    conn.commit()
    conn.close()
    return {"onboarding_step_question_step": len(data["steps"]),
            "onboarding_step_question": len(questions),
            "onboarding_step_question_target": len(targets),
            "onboarding_step_question_option": len(options)}


if __name__ == "__main__":
    for table, n in load_step_questions().items():
        print(f"loaded {n} rows into engine_internal.{table}")
