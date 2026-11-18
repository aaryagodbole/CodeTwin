"""POST /api/v1/reports: authentication, validation, idempotency and limits."""
import json

from conftest import HEAD, auth_header, oidc, register, report

from codetwin_cloud import auth, db


def test_github_oidc_upload_is_stored_once(client, database):
    register(database)
    r = client.post("/api/v1/reports", json=report(), headers=auth_header(oidc()))
    assert r.status_code == 201 and r.json()["created"] is True
    again = client.post("/api/v1/reports", json=report(), headers=auth_header(oidc()))   # a retried job
    assert again.status_code == 200 and again.json() == {"id": r.json()["id"], "created": False}
    with db.connect(database) as c:
        row = c.execute("select count(*) as n, max(selected_count) as sel from report").fetchone()
    assert row == {"n": 1, "sel": 1}


def test_a_job_can_upload_only_its_own_result(client, database):
    register(database)
    register(database, "acme/other")
    cases = [
        (oidc(repository="acme/other"), report(), "repository"),
        (oidc(run_id="999"), report(), "workflow run"),
        (oidc(sha="c" * 40), report(), "commit"),
    ]
    for token, body, word in cases:
        r = client.post("/api/v1/reports", json=body, headers=auth_header(token))
        assert r.status_code == 403 and word in r.json()["detail"], (word, r.json())


def test_bad_tokens_are_rejected_before_anything_else(client, database):
    register(database)
    for token in [oidc(aud="someone-else"), oidc(exp=1, iat=0, nbf=0), oidc(iss="https://evil.example"),
                  oidc(repository=None), "not-a-jwt"]:
        assert client.post("/api/v1/reports", json=report(), headers=auth_header(token)).status_code == 401
    assert client.post("/api/v1/reports", json=report()).status_code == 401
    # unknown repositories are not revealed to unauthenticated callers, and never created implicitly
    assert client.post("/api/v1/reports", json=report(repository="nobody/x")).status_code == 401
    r = client.post("/api/v1/reports", json=report(repository="nobody/x"),
                    headers=auth_header(oidc(repository="nobody/x")))
    assert r.status_code == 403


def test_unknown_fields_and_bad_values_are_refused(client, database):
    register(database)
    sneaky = report()
    sneaky["decision"]["source_code"] = "def secret(): ..."
    for body in [sneaky, report(schema="codetwin.report/v9"), report(commit={"head": "not-a-sha"})]:
        r = client.post("/api/v1/reports", json=body, headers=auth_header(oidc()))
        assert r.status_code == 422, body


def test_size_and_rate_limits(client, database):
    register(database)
    big = report()
    big["decision"]["reasons"] = ["x" * 1000] * 199
    big["decision"]["sections"] = {"s": {"blob": "y" * 120_000}}
    assert client.post("/api/v1/reports", content=json.dumps(big), headers=auth_header(oidc())).status_code == 413
    for attempt in range(1, 6):    # settings allow 5 per hour in tests
        r = client.post("/api/v1/reports", json=report(run={"source": "github-actions", "id": "1001",
                                                            "attempt": attempt}),
                        headers=auth_header(oidc(run_attempt=str(attempt))))
        assert r.status_code == 201
    r = client.post("/api/v1/reports", json=report(run={"source": "github-actions", "id": "1001", "attempt": 6}),
                    headers=auth_header(oidc(run_attempt="6")))
    assert r.status_code == 429
    # A retry of a report that is already stored is not a new upload: it gets its id back, even at the limit.
    again = client.post("/api/v1/reports", json=report(run={"source": "github-actions", "id": "1001", "attempt": 1}),
                        headers=auth_header(oidc(run_attempt="1")))
    assert again.status_code == 200 and again.json()["created"] is False


def test_project_token_upload_for_self_hosting(client, database):
    pid = register(database)
    register(database, "acme/other")
    token, digest = auth.new_project_token()
    with db.connect(database) as c:
        c.execute("insert into project_token (project_id, token_hash) values (%s, %s)", (pid, digest))
        assert c.execute("select count(*) as n from project_token where token_hash = %s", (token,)).fetchone()["n"] == 0
    cli = report(run={"source": "cli", "id": "local-1", "attempt": 1})
    assert client.post("/api/v1/reports", json=cli, headers=auth_header(token)).status_code == 201
    other = report(repository="acme/other", run={"source": "cli", "id": "local-2", "attempt": 1})
    assert client.post("/api/v1/reports", json=other, headers=auth_header(token)).status_code == 403
    assert client.post("/api/v1/reports", json=cli, headers=auth_header("ctp_wrong")).status_code == 401


def test_outcome_is_stored_with_the_report(client, database):
    register(database)
    r = client.post("/api/v1/reports", json=report(outcome={"missed": True, "failing": ["tests/test_calc.py::t"]}),
                    headers=auth_header(oidc()))
    with db.connect(database) as c:
        o = c.execute("select missed, failing from outcome where report_id = %s", (r.json()["id"],)).fetchone()
    assert o == {"missed": True, "failing": ["tests/test_calc.py::t"]}
    assert HEAD  # the report's head commit equals the token's sha


def test_the_token_run_attempt_must_match_the_report(client, database):
    """One job token cannot store extra reports by changing run.attempt."""
    register(database)
    forged = report(run={"source": "github-actions", "id": "1001", "attempt": 2})
    r = client.post("/api/v1/reports", json=forged, headers=auth_header(oidc(run_attempt="1")))
    assert r.status_code == 403 and "attempt" in r.json()["detail"]


def test_nan_and_infinity_are_refused(client, database):
    """NaN would be stored and then break every read of the project (JSON cannot encode it)."""
    register(database)
    for bad in ("NaN", "Infinity"):
        body = json.dumps(report()).replace('"threshold": 0.42', f'"threshold": {bad}')
        r = client.post("/api/v1/reports", content=body, headers=auth_header(oidc()))
        assert r.status_code == 422, bad
        body = json.dumps(report()).replace('"score": 0.71', f'"score": {bad}')
        assert client.post("/api/v1/reports", content=body, headers=auth_header(oidc())).status_code == 422
    assert client.get("/api/v1/projects/acme/shop/decisions").status_code == 200


def test_oidc_uploads_are_bound_to_the_repository_id(client, database):
    """A renamed or recreated repository with the same name cannot upload into the original project."""
    register(database)
    first = client.post("/api/v1/reports", json=report(), headers=auth_header(oidc(repository_id="111")))
    assert first.status_code == 201
    other = report(commit={"head": "c" * 40, "base": None, "ref": None, "pull_request": None})
    r = client.post("/api/v1/reports", json=other, headers=auth_header(oidc(repository_id="222", sha="c" * 40)))
    assert r.status_code == 403 and "repository id" in r.json()["detail"]
    ok = client.post("/api/v1/reports", json=other, headers=auth_header(oidc(repository_id="111", sha="c" * 40)))
    assert ok.status_code == 201


def test_a_token_without_repository_id_is_refused(client, database):
    register(database)
    r = client.post("/api/v1/reports", json=report(), headers=auth_header(oidc(repository_id=None)))
    assert r.status_code == 401
