"""Run the API: `python -m sahacore.api`.

The Docker image invokes uvicorn directly so its arguments are visible in
the image's CMD rather than buried here, but this entrypoint exists so the
same server can be started identically outside a container -- and so that
uvicorn is imported by the source tree rather than only named in a
Dockerfile, which is what tests/test_requirements_cover_imports.py insists
on for every pinned dependency.
"""
import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "sahacore.api:app",
        host=os.environ.get("SAHACORE_HOST", "127.0.0.1"),
        port=int(os.environ.get("SAHACORE_PORT", "8000")),
        log_level=os.environ.get("SAHACORE_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
