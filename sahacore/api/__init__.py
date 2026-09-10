"""SahaCore's HTTP surface.

`from sahacore.api import app` is what a WSGI/ASGI runner wants;
`python -m sahacore.api` runs it directly. See sahacore/api/app.py.
"""
from sahacore.api.app import app, create_app

__all__ = ["app", "create_app"]
