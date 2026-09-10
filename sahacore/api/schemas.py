"""Request and response shapes for the SahaCore API.

These mirror `sahacore.ledger.ingest.ingest_event`'s signature rather than
inventing a wire format. Where they differ from it, the difference is
deliberate and commented -- there is exactly one such difference, and it is
`ingested_at`.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    """One raw event, as an adapter delivers it.

    THERE IS NO `ingested_at` FIELD, AND THAT IS THE POINT. The ledger's
    knowledge clock records when THIS SYSTEM learned a fact, and a caller
    that could set it could rewrite that history -- backdating a late
    delivery so a replay believes the engine knew something it did not. The
    server stamps it on arrival. Every other clock IS the source's to state,
    because those describe when the observation happened, not when we heard.
    """

    # EXTRA FIELDS ARE REFUSED, NOT IGNORED. Pydantic's default is to drop
    # what it does not recognise, which would let a caller send
    # `ingested_at`, receive 201, and believe they had set the knowledge
    # clock. Silently discarding it is the worst of the three options --
    # worse than honouring it, because nothing tells the caller. A 422 says
    # exactly what happened.
    model_config = ConfigDict(extra="forbid")

    adapter_source_id: str = Field(min_length=1, max_length=200)
    source_event_id: str = Field(min_length=1, max_length=200)
    user_id: UUID
    event_type: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any]

    occurred_at: datetime | None = None
    specimen_at: datetime | None = None
    observed_at: datetime | None = None
    adapter_effective_at: datetime | None = None
    accepted_at: datetime | None = None
    source_timezone: str | None = None
    quality: str | None = None

    # A correction is a NEW event pointing at the one it corrects; it never
    # overwrites it. See the ledger's ingest docstring.
    correction_of_event_id: UUID | None = None


class EventAccepted(BaseModel):
    """What the ledger holds for this fact after the call.

    On a duplicate every field describes the ORIGINAL row, so a caller
    logging this response cannot publish the rejected second payload as
    though it had been accepted.
    """

    event_uuid: UUID
    ingest_seq: int
    effective_at: datetime
    knowledge_at: datetime
    clock_quarantined: bool
    lineage_hash: str
    is_duplicate: bool


class DatabaseStatus(BaseModel):
    configured: bool
    reachable: bool
    migrations_applied: int | None = None
    detail: str | None = None


class Health(BaseModel):
    status: str
    service: str
    database: DatabaseStatus
