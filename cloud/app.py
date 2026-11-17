"""Vercel entry point: Vercel's Python runtime looks for a FastAPI instance named `app` here (cloud/README.md)."""
import logging
import sys

from codetwin_cloud.app import create_app

# One JSON line per request on stdout (Vercel collects it as the function log). Configured on our own logger,
# because the server (uvicorn locally, Vercel's runtime) may already have configured the root logger.
_log = logging.getLogger("codetwin_cloud")
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False

app = create_app()
