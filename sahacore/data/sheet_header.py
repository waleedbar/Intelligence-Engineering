"""One header check, used by every extractor, that refuses a partial table.

WHY THIS IS SHARED RATHER THAN COPIED. Each extractor used to carry its own
loop over a list of expected labels. That verifies the columns you thought to
name and says nothing about the ones you did not, so a sheet with a seventh
column and an extractor that declares six agree perfectly and lose the
seventh in silence.

That is exactly what happened. 'O·O1 Anthropometrics' and 'O·O2 MVPA Prior'
both carry an "Engine Target" column -- where each equation's output goes,
"Layer C: Z3 Inflammation rate", "Layer B (B1): V_f" -- and both were
imported without it. So was 'TVMCD · 15 Pathways Build', whose extractor
dropped "Uncertainty treatment" and "Validation scenario" while its own
docstring called the sheet a complete implementation table and its check()
refused empty columns.

None of those failed anything. A missing column is invisible to a check that
only looks at the columns it was given.

So `check_header` does both halves: the labels must match, AND the cell after
the last one must be empty. A sheet that grows a column now stops the
extract, which is the only moment anyone is going to read it.
"""


def check_header(ws, sheet: str, row: int, first_col: int,
                 labels: list[str], followed_by: list[str] | None = None) -> None:
    """Verify a header row completely: the declared labels, and that nothing
    follows them.

    `ws` is an openpyxl worksheet, `row` the 1-based header row, `first_col`
    the 1-based column the table starts in, `labels` every column the
    extractor intends to read, in order.
    """
    for offset, expected in enumerate(labels):
        found = ws.cell(row=row, column=first_col + offset).value
        found = None if found is None else str(found).strip()
        if found != expected:
            raise SystemExit(
                f"{sheet}: header row {row} column {first_col + offset} reads "
                f"{found!r}, expected {expected!r}. The sheet moved; fix the "
                "offsets rather than the expectation.")

    # A table's columns are contiguous, so the scan stops at the first empty
    # cell. This is the honest limit of the check: a sheet that puts a gap
    # and then more columns of the SAME table would still slip through. In
    # this workbook headers are contiguous, and scanning a fixed distance
    # instead reaches into the wide numeric grids that sit further along the
    # same row -- 'Live Verification Lab' row 173 has data at column H.
    trailing = []
    offset = len(labels)
    while True:
        value = ws.cell(row=row, column=first_col + offset).value
        if value is None:
            break
        trailing.append(str(value).strip())
        offset += 1

    # A few header rows carry two tables side by side -- 'Live Verification
    # Lab' row 173 has Input|Value at column A and Derived quantity|Formula
    # result at column D. A caller may declare what follows, and the check
    # then holds it to exactly that: naming the neighbour is a decision on
    # the record, and a THIRD table appearing still stops the extract.
    if followed_by is not None:
        if trailing[:len(followed_by)] != followed_by:
            raise SystemExit(
                f"{sheet}: header row {row} declares a neighbouring table "
                f"{followed_by}, but what follows is {trailing}.")
        trailing = trailing[len(followed_by):]

    if trailing:
        raise SystemExit(
            f"{sheet}: header row {row} carries {len(trailing)} column(s) "
            f"past the last one this extractor declares: {trailing}. The "
            "sheet holds more than is being imported -- read the new "
            "column(s) and add them, rather than widening the range.")
