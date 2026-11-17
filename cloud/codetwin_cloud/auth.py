"""Upload authentication (docs/cloud.md, "Upload authentication").

- GitHub Actions: an OIDC ID token (short-lived, issued per job). Verified against GitHub's published keys; the
  token's claims must match the report (repository, run id, commit), so a job can upload only its own result.
- Self-hosted / CI without OIDC: a per-project token `ctp_...`; only its SHA-256 is stored.
Tokens are never stored or logged.
"""
from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

GITHUB_ISSUER = "https://token.actions.githubusercontent.com"
GITHUB_JWKS = f"{GITHUB_ISSUER}/.well-known/jwks"
AUDIENCE = "codetwin-cloud"
TOKEN_PREFIX = "ctp_"  # noqa: S105  a public prefix, not a secret

KeyResolver = Callable[[str], Any]    # token -> verification key (tests inject their own)


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Caller:
    kind: str                          # "github-oidc" or "project-token"
    repository: str | None = None      # owner/name from the OIDC token
    run_id: str | None = None
    run_attempt: int | None = None
    sha: str | None = None
    project_id: int | None = None      # from a project token


_jwks_client: jwt.PyJWKClient | None = None


def github_key(token: str) -> Any:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GITHUB_JWKS, cache_keys=True, lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_github_oidc(token: str, resolve_key: KeyResolver = github_key, audience: str = AUDIENCE) -> Caller:
    try:
        claims = jwt.decode(token, resolve_key(token), algorithms=["RS256"], audience=audience, issuer=GITHUB_ISSUER,
                            leeway=60, options={"require": ["exp", "iat", "iss", "aud", "repository", "run_id", "sha"]})
    except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
        raise AuthError(401, f"invalid GitHub OIDC token: {e}") from None
    return Caller("github-oidc", repository=str(claims["repository"]), run_id=str(claims["run_id"]),
                  run_attempt=int(claims.get("run_attempt", 1)), sha=str(claims["sha"]))


def new_project_token() -> tuple[str, str]:
    """(token shown once to the user, hash to store)."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def bearer(header: str | None) -> str:
    if not header or not header.lower().startswith("bearer "):
        raise AuthError(401, "missing Authorization: Bearer <token>")
    return header.split(" ", 1)[1].strip()
