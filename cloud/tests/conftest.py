"""Tests run against a real Postgres: set CODETWIN_TEST_DATABASE_URL (CI provides a service container; locally see
cloud/README.md). Every test gets an empty schema. OIDC tokens are signed with a throwaway RSA key."""
from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from codetwin_cloud import db
from codetwin_cloud.app import Settings, create_app
from codetwin_cloud.auth import AUDIENCE, GITHUB_ISSUER

URL = os.environ.get("CODETWIN_TEST_DATABASE_URL")
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
HEAD = "a" * 40
BASE = "b" * 40


@pytest.fixture
def database() -> Iterator[str]:
    if not URL:
        pytest.skip("CODETWIN_TEST_DATABASE_URL not set (needs Postgres; see cloud/README.md)")
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("drop schema public cascade")
        c.execute("create schema public")
    db._migrated.discard(URL)
    yield URL


@pytest.fixture
def settings(database: str) -> Settings:
    return Settings(database_url=database, resolve_key=lambda _token: KEY.public_key(), cron_secret="cron-test",
                    uploads_per_hour=5)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def register(url: str, repository: str = "acme/shop", public: bool = True) -> int:
    owner, name = repository.split("/")
    with db.connect(url) as c:
        row = c.execute("insert into project (owner, name, public) values (%s, %s, %s) returning id",
                        (owner, name, public)).fetchone()
    return row["id"]


def oidc(**over: Any) -> str:
    now = int(time.time())
    claims = {"iss": GITHUB_ISSUER, "aud": AUDIENCE, "iat": now, "nbf": now, "exp": now + 300,
              "repository": "acme/shop", "repository_id": "111", "run_id": "1001", "run_attempt": "1", "sha": HEAD,
              "sub": "repo:acme/shop:pull_request"}
    claims.update(over)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, KEY, algorithm="RS256")


def report(**over: Any) -> dict:
    r: dict[str, Any] = {
        "schema": "codetwin.report/v1",
        "engine": {"version": "0.2.0", "output_schema": 1},
        "repository": "acme/shop",
        "commit": {"head": HEAD, "base": BASE, "ref": "refs/pull/7/merge", "pull_request": 7},
        "run": {"source": "github-actions", "id": "1001", "attempt": 1},
        "decision": {"decision": "proceed", "residual_risk": 0.031, "alpha": 0.1, "threshold": 0.42,
                     "mode": "calibrated", "selected": ["tests/test_cart.py"],
                     "tests": [{"id": "tests/test_cart.py", "selected": True, "score": 0.71, "seconds": 0.4},
                               {"id": "tests/test_calc.py", "selected": False, "score": 0.02, "seconds": 0.2}],
                     "reasons": ["estimated residual risk 3.1% <= target 10%"],
                     "sections": {"changed_files": {"summary": "1 file changed", "files": ["src/shop/calc.py"]}}},
        "outcome": None,
    }
    r.update(over)
    return r


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
