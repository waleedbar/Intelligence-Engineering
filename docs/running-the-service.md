# Running SahaCore

Three ways, in increasing order of how much they prove.

## 1. Locally, no container

```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql://user:pass@host:5432/sahacore'
python -m sahacore.migrate          # apply schema
python -m sahacore.api              # serve on 127.0.0.1:8000
```

`python -m sahacore.api` binds **127.0.0.1** deliberately. The container
overrides this to `0.0.0.0` in its `CMD`, because inside a container that is
the only useful bind — but a workstation should not expose a port to the
network because someone typed the wrong command.

## 2. The image

```bash
docker build -t sahacore:dev .
docker run --rm -p 8000:8000 -e DATABASE_URL='...' sahacore:dev
```

The image serves the API **and** contains the suite, on purpose. A test image
built from different layers proves nothing about the image that ships:

```bash
docker run --rm -e DATABASE_URL= sahacore:dev python -m pytest tests/ -q
```

It runs as uid **10001**, owns none of its own source, and its `HEALTHCHECK`
probes `/health` — the liveness endpoint, never `/health/ready`. Docker
restarts an unhealthy container, so wiring the readiness probe there would
turn a database blip into a crash loop.

## 3. Compose, with a real database

This is the one that runs the whole suite, including the 138 tests that need
PostgreSQL:

```bash
docker compose run --rm tests      # migrations first, then the full suite
docker compose up api              # http://localhost:8000
```

`migrate` runs to completion before either, so nothing starts against an
unmigrated database. The database publishes no port: the API and the tests
reach it on the compose network and nothing outside needs to.

CI does all of this on every push — see the `docker` job in
`.github/workflows/ci.yml`, which builds the image, runs the suite inside it
twice (with and without a database), starts the real `CMD` and probes both
health endpoints, and asserts the container is not running as root.

---

## The endpoints

| | |
|---|---|
| `GET /health` | Liveness. **200 whatever the database is doing**, with its condition in the body. |
| `GET /health/ready` | Readiness. **503** unless the database is reachable *and* migrated. |
| `POST /v1/events` | Admit one raw event. **201** if new, **200** if already held. |
| `GET /docs` | OpenAPI, generated from the schemas. |

### Why two health endpoints

They answer different questions. Liveness asks *"is this process alive?"* —
a probe that fails on a database blip restarts a perfectly good container and
makes the outage worse. Readiness asks *"should traffic come here?"* — and an
ingestion request against an unmigrated database is a 500 waiting to happen,
so readiness refuses traffic first.

### What the ingestion endpoint will not let you do

**Set `ingested_at`.** It is not a field on the request model, and unknown
fields are *rejected* rather than ignored — pydantic's default is to drop
them, which would let a caller send `ingested_at`, receive `201`, and believe
they had set the knowledge clock. That clock records when *this system*
learned a fact; a caller able to set it could backdate a late delivery so a
replay believes the engine knew something it did not.

Every other clock **is** the source's to state: those describe when the
observation happened, not when we heard about it.

**Send an event with no physiological time.** `'Replay Contract'` section B
refuses to resolve one — ingestion time is explicitly not a physiological
clock, because a filter updated at the moment of *delivery* rather than the
moment of *observation* is measuring the network. That is a malformed event,
so it is a **422** carrying the ledger's own message about which clock is
missing, not a 500.

### Why a duplicate is 200 and not 201

`'Replay Contract'` section F, RT-02 (RELEASE_BLOCKING): a second delivery of
the same fact must be a no-op. An adapter that retries needs to be able to
tell that its retry was *absorbed* rather than double-counted — and the body
of a 200 describes the **original** row, so a caller logging the response
cannot publish the rejected second payload as though it had been accepted.

## What this API is not, yet

It opens **a connection per request** rather than using a pool. That is a
deliberate omission: a pool is configuration nobody has chosen yet, and
`sahacore.db.get_connection` is the single place it will go.

It holds **no engine logic**. An equation implemented at the HTTP edge would
be an equation with no sheet behind it.
