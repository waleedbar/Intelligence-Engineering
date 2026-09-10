"""The SahaCore HTTP surface: liveness, readiness, and event ingestion.

WHAT THIS IS AND IS NOT. It is a thin edge over `sahacore.ledger`. It holds
no engine logic of its own: an equation implemented here would be an equation
with no sheet behind it, which is the one thing this repo refuses. Its whole
job is to turn an HTTP request into the ledger call the Replay Contract
already specifies, and to fail honestly when it cannot.

TWO HEALTH ENDPOINTS, BECAUSE THEY ANSWER DIFFERENT QUESTIONS.

    GET /health        Is the process alive? Answers 200 whatever the
                       database is doing, and reports what it found in the
                       body. A liveness probe that fails on a database blip
                       restarts a perfectly good container and makes the
                       outage worse.

    GET /health/ready  Should traffic be sent here? 503 unless the database
                       is reachable AND migrations have been applied, because
                       an ingestion request against an unmigrated database is
                       a 500 waiting to happen.

Docker's HEALTHCHECK and a Kubernetes livenessProbe want the first; a
readinessProbe and a load balancer want the second.

THE INGESTION ENDPOINT IS A STUB IN ONE RESPECT ONLY: it opens a connection
per request rather than using a pool. That is a deliberate omission, not an
oversight -- a pool is configuration this build has not been asked to choose
yet, and `sahacore.db.get_connection` is the single place it will be added.
Everything else about the path is the real one: the same idempotency, the
same clock resolution, the same lineage hash.

HTTP STATUS CARRIES THE LEDGER'S IDEMPOTENCY.

    201 Created   this fact is new
    200 OK        this fact was already held; the body describes the
                  ORIGINAL row and nothing was written

That distinction is not decoration. 'Replay Contract' section F, RT-02
(RELEASE_BLOCKING) requires a second delivery of the same lab to be a no-op,
and an adapter that retries needs to be able to tell that its retry was
absorbed rather than double-counted.
"""
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Response, status

from sahacore.api.schemas import (
    DatabaseStatus,
    EventAccepted,
    EventIn,
    Health,
)

SERVICE_NAME = "sahacore"


def _database_status() -> DatabaseStatus:
    """Probe the database without letting a failure escape.

    Every failure mode reports rather than raises, because both callers --
    liveness and readiness -- need to decide what to do about it themselves.
    """
    if not os.environ.get("DATABASE_URL"):
        return DatabaseStatus(
            configured=False,
            reachable=False,
            detail="DATABASE_URL is not set",
        )
    try:
        from sahacore.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Cheap, and it proves the connection can actually execute
                # rather than merely open.
                cur.execute("SELECT count(*) AS n FROM schema_migrations")
                applied = cur.fetchone()["n"]
        finally:
            conn.close()
        return DatabaseStatus(
            configured=True, reachable=True, migrations_applied=applied
        )
    except Exception as error:                      # noqa: BLE001
        # The class name, not the message: a psycopg connection error can
        # carry the DSN, and a health endpoint is often the least
        # authenticated thing a service exposes.
        return DatabaseStatus(
            configured=True,
            reachable=False,
            detail=type(error).__name__,
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="SahaCore",
        version="0.1.0",
        summary="Ledger ingestion and health for the SahaPlus AI engine.",
    )

    @app.get("/health", response_model=Health, tags=["health"])
    def health() -> Health:
        """Liveness. 200 while the process is serving, whatever the database
        is doing -- the database's condition is reported in the body."""
        database = _database_status()
        return Health(
            status="ok" if database.reachable else "degraded",
            service=SERVICE_NAME,
            database=database,
        )

    @app.get("/health/ready", response_model=Health, tags=["health"])
    def ready(response: Response) -> Health:
        """Readiness. 503 unless the database is reachable and migrated."""
        database = _database_status()
        healthy = database.reachable and bool(database.migrations_applied)
        if not healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(
            status="ready" if healthy else "not_ready",
            service=SERVICE_NAME,
            database=database,
        )

    @app.post(
        "/v1/events",
        response_model=EventAccepted,
        status_code=status.HTTP_201_CREATED,
        tags=["ledger"],
    )
    def ingest(event: EventIn, response: Response) -> EventAccepted:
        """Admit one raw event.

        `ingested_at` is stamped HERE, on arrival, and is not accepted from
        the caller -- see EventIn.
        """
        if not os.environ.get("DATABASE_URL"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ledger unavailable: DATABASE_URL is not set",
            )

        from sahacore.db import get_connection
        from sahacore.ledger import ingest_event
        from sahacore.ledger.times import ClockResolutionError

        # Stamped before the connection is opened, so a slow pool checkout
        # cannot drift the knowledge clock away from the arrival time.
        ingested_at = datetime.now(timezone.utc)

        conn = get_connection()
        try:
            result = ingest_event(
                conn,
                ingested_at=ingested_at,
                **event.model_dump(),
            )
            conn.commit()
        except ClockResolutionError as error:
            # THE CALLER'S FAULT, NOT OURS. The ledger refuses an event with
            # no physiological time -- 'Replay Contract' section B is
            # explicit that ingestion time is not one, because a filter
            # updated at the moment of delivery rather than the moment of
            # observation is measuring the network. That is a malformed
            # event, so it is a 422 and not the 500 an unhandled exception
            # would produce. The ledger's own message says which clock is
            # missing, so it is passed through rather than replaced.
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        if result.is_duplicate:
            # Already held. Nothing was written and the body below describes
            # the original row, so this is not a creation.
            response.status_code = status.HTTP_200_OK
        return EventAccepted(**vars(result))

    return app


app = create_app()
