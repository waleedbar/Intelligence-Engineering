"""The two clocks.

Source: v39sEng2.xlsx, sheet 'Replay Contract', section B ("THE TWO CLOCKS")
and section A step 1, whose rule is transcribed verbatim:

    "Resolve the two clocks. effective_at is when physiology was affected:
     specimen_at for a laboratory sample; otherwise the adapter-defined event
     time. knowledge_at is when the engine received/accepted the fact,
     normally ingested_at."

    Acceptance test (cell G7): "effective_at<=knowledge_at; lab uses
    specimen_at; timezone normalized to UTC"

Section B's field definitions, also verbatim:

    effective_at  "When the event affected physiology. Laboratory default:
                   specimen_at. Other events: occurred_at or adapter-defined
                   physiological time."
                  Validation: "UTC; not after knowledge_at except clock-error
                   quarantine"
                  Do not use as: "The date the result was uploaded"
    knowledge_at  "When the engine first accepted the information, normally
                   ingested_at."
                  Validation: "monotone system time"
                  Do not use as: "The physiological event time"
    observed_at   "When a sensor/device or observer recorded a reading; may
                   equal effective_at for real-time sensors."
                  Do not use as: "A universal replacement for specimen_at"

The sheet's analogy for why these must not be collapsed into one column: a
late lab result is "the date the photograph was taken" versus "the date the
photograph reached the detective".

The clock-error escape is deliberately a returned FLAG, not an exception.
Section B's validation cell allows effective_at > knowledge_at only under
"clock-error quarantine", so a device with a skewed clock must still be
admitted as an immutable fact -- an event the ledger refuses to store is an
event that can never be corrected or replayed -- but it is marked, and
sql/009_ledger.sql's CHECK constraint accepts such a row only when the flag
is set. Nothing is ever silently accepted.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


class ClockResolutionError(ValueError):
    """Raised when an event carries no timestamp that can serve as
    effective_at, or carries one whose timezone is unknown. Both are
    unresolvable: the sheet requires a UTC-normalised physiological time on
    every raw_event, and neither can be invented from the payload."""


# 'lab' is the one event_type whose effective_at is fixed by the sheet
# ("Laboratory default: specimen_at", and step 3 distinguishes labs by
# specimen_at again). Every other type resolves through the adapter contract.
LABORATORY_EVENT_TYPE = "lab"


@dataclass(frozen=True)
class ResolvedTimes:
    """The bitemporal pair written onto every raw_event, plus the quarantine
    flag that records whether the pair satisfied effective_at <= knowledge_at
    on its own or needed section B's named clock-error escape."""

    effective_at: datetime
    knowledge_at: datetime
    clock_quarantined: bool


def _as_utc(value: datetime, field_name: str) -> datetime:
    """G7: "timezone normalized to UTC". A naive datetime is rejected rather
    than assumed to be UTC: guessing a zone would silently move a meal or a
    specimen draw by up to a day, which is exactly the error the two-clock
    design exists to prevent."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ClockResolutionError(
            f"{field_name} has no timezone; the ledger cannot normalise it to UTC"
        )
    return value.astimezone(timezone.utc)


def resolve_times(
    *,
    event_type: str,
    ingested_at: datetime,
    occurred_at: datetime | None = None,
    specimen_at: datetime | None = None,
    observed_at: datetime | None = None,
    adapter_effective_at: datetime | None = None,
    accepted_at: datetime | None = None,
) -> ResolvedTimes:
    """Step 1 of the Replay Contract, as a pure function of one event's
    timestamps.

    `adapter_effective_at` is the sheet's "adapter-defined physiological
    time": when an adapter knows better than occurred_at what moment actually
    affected physiology, it says so, and that wins for non-lab events.

    `accepted_at` covers B22's "normally ingested_at" -- normally, but an
    event held in quarantine and accepted later has a knowledge_at that is
    not its ingestion time. Omitted, knowledge_at is ingested_at.
    """
    knowledge_at = _as_utc(
        ingested_at if accepted_at is None else accepted_at,
        "accepted_at" if accepted_at is not None else "ingested_at",
    )

    if event_type == LABORATORY_EVENT_TYPE:
        if specimen_at is None:
            raise ClockResolutionError(
                "a lab event has no specimen_at; the Replay Contract fixes "
                "effective_at=specimen_at for laboratory samples, and the "
                "upload time is explicitly not a substitute"
            )
        effective_at = _as_utc(specimen_at, "specimen_at")
    else:
        # "otherwise the adapter-defined event time" -- adapter override
        # first, then the logged event time, then, for a real-time sensor
        # with no separate event time, the moment the reading was recorded
        # (B23: observed_at "may equal effective_at for real-time sensors").
        for candidate, name in (
            (adapter_effective_at, "adapter_effective_at"),
            (occurred_at, "occurred_at"),
            (observed_at, "observed_at"),
        ):
            if candidate is not None:
                effective_at = _as_utc(candidate, name)
                break
        else:
            raise ClockResolutionError(
                f"a {event_type!r} event carries no adapter_effective_at, "
                "occurred_at or observed_at; there is no physiological time "
                "to resolve, and ingested_at is explicitly not one"
            )

    return ResolvedTimes(
        effective_at=effective_at,
        knowledge_at=knowledge_at,
        clock_quarantined=effective_at > knowledge_at,
    )


def lag(effective_at: datetime, knowledge_at: datetime) -> float:
    """How late this fact arrived, in days: the gap the Replay Contract's
    step 11 compares against the configured fixed lag L_smooth. Zero for a
    fact learned at the moment it happened; negative only for a quarantined
    clock error."""
    return (knowledge_at - effective_at).total_seconds() / 86400.0
