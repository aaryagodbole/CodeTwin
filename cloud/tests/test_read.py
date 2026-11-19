"""Read endpoints keep the response shapes of `codetwin serve`, so the dashboard works against either."""
import json
from pathlib import Path

from conftest import auth_header, oidc, register, report

from codetwin_cloud import db

DEMO = Path(__file__).resolve().parents[2] / "dashboard" / "public" / "demo" / "api"


def upload_two(client):
    client.post("/api/v1/reports", json=report(outcome={"missed": False, "failing": []}), headers=auth_header(oidc()))
    second = report(run={"source": "github-actions", "id": "1002", "attempt": 1},
                    outcome={"missed": True, "failing": ["tests/test_calc.py::test_add"]})
    second["decision"]["decision"] = "abstain"
    client.post("/api/v1/reports", json=second, headers=auth_header(oidc(run_id="1002")))


def test_contract_matches_the_local_api(client, database):
    """Same keys as the local API answers saved in the dashboard demo snapshot (scripts/demo_snapshot.py)."""
    register(database)
    upload_two(client)
    base = "/api/v1/projects/acme/shop"
    local_summary = json.loads((DEMO / "summary.json").read_text())
    assert set(client.get(f"{base}/summary").json()) == set(local_summary)
    local_rows = json.loads((DEMO / "decisions__limit-10.json").read_text())
    cloud_rows = client.get(f"{base}/decisions", params={"limit": 10}).json()
    assert [set(r) for r in cloud_rows] == [set(local_rows[0])] * 2
    local_cal = json.loads((DEMO / "calibration.json").read_text())
    cloud_cal = client.get(f"{base}/calibration").json()
    assert set(cloud_cal) == set(local_cal) and set(cloud_cal["points"][0]) == set(local_cal["points"][0])


def test_read_values(client, database):
    register(database)
    upload_two(client)
    base = "/api/v1/projects/acme/shop"
    rows = client.get(f"{base}/decisions").json()
    assert [r["decision"] for r in rows] == ["abstain", "proceed"]          # newest first
    assert [r["missed"] for r in rows] == [True, False]
    detail = client.get(f"{base}/decisions/{rows[1]['id']}").json()
    assert detail["scores"] == {"tests/test_cart.py": 0.71, "tests/test_calc.py": 0.02}
    assert detail["sections"]["changed_files"]["files"] == ["src/shop/calc.py"]
    assert detail["commit"]["pull_request"] == 7
    assert client.get(f"{base}/decisions/999999").status_code == 404
    cal = client.get(f"{base}/calibration").json()
    assert cal["labelled"] == 2 and cal["misses"] == 1 and cal["points"][-1]["observed_miss_rate"] == 0.5
    s = client.get(f"{base}/summary").json()
    assert s["decisions"] == 2 and s["labelled_decisions"] == 2 and s["test_files"] == 2
    assert s["suite_seconds"] == 0.6000000000000001 or abs(s["suite_seconds"] - 0.6) < 1e-9
    assert client.get("/api/v1/projects").json()[0] | {"last_report": None} == \
        {"owner": "acme", "name": "shop", "reports": 2, "last_report": None}


def test_private_and_unknown_projects_are_not_readable(client, database):
    register(database, "acme/secret", public=False)
    assert client.get("/api/v1/projects/acme/secret/decisions").status_code == 404
    assert client.get("/api/v1/projects/nobody/x/summary").status_code == 404
    assert client.get("/api/v1/projects").json() == []


def test_health_and_retention(client, database, settings):
    assert client.get("/api/health").json()["database"] == "ok"
    register(database)
    upload_two(client)
    assert client.get("/api/cron/retention").status_code == 401
    with db.connect(database) as c:
        c.execute("update report set received_at = now() - interval '91 days' where run_id = '1001'")
    r = client.get("/api/cron/retention", headers={"Authorization": "Bearer cron-test"})
    assert r.json() == {"deleted": 1, "retention_days": 90}
    assert len(client.get("/api/v1/projects/acme/shop/decisions").json()) == 1


def test_health_reports_a_broken_database():
    from fastapi.testclient import TestClient

    from codetwin_cloud.app import Settings, create_app
    bad = TestClient(create_app(Settings(database_url="postgresql://nobody@127.0.0.1:1/none")))
    r = bad.get("/api/health")
    assert r.status_code == 503 and r.json()["database"] == "unavailable"


def test_migrations_apply_once(database):
    with db.connect(database) as c:
        assert db.migrate(c) == []
        names = [r["name"] for r in c.execute("select name from schema_migrations order by name").fetchall()]
    assert names == [name for name, _sql in db.migration_files()]
    assert names[0] == "0001_initial.sql"


def test_out_of_range_decision_id_is_not_found(client, database):
    register(database)
    big = 2**70
    assert client.get(f"/api/v1/projects/acme/shop/decisions/{big}").status_code == 404


def test_cors_origins_ignore_spaces(monkeypatch):
    from codetwin_cloud.app import Settings

    monkeypatch.setenv("CODETWIN_CORS_ORIGINS", "https://a.example, https://b.example ,")
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_add_project_again_keeps_it_public(database, monkeypatch):
    from codetwin_cloud.__main__ import main

    monkeypatch.setenv("DATABASE_URL", database)
    assert main(["add-project", "acme/shop", "--public"]) == 0
    assert main(["add-project", "acme/shop", "--token"]) == 0           # only to get a token
    with db.connect(database) as c:
        assert c.execute("select public from project").fetchone() == {"public": True}
    assert main(["add-project", "acme/shop", "--private"]) == 0
    with db.connect(database) as c:
        assert c.execute("select public from project").fetchone() == {"public": False}


def test_calibration_counts_only_calibrated_decisions_like_the_local_api(client, database):
    register(database)
    for attempt, mode, missed in [(1, "calibrated", True), (2, "full", False), (3, "calibrated", False)]:
        body = report(run={"source": "github-actions", "id": "1001", "attempt": attempt},
                      outcome={"missed": missed, "failing": []})
        body["decision"]["mode"] = mode
        assert client.post("/api/v1/reports", json=body,
                           headers=auth_header(oidc(run_attempt=str(attempt)))).status_code == 201
    cal = client.get("/api/v1/projects/acme/shop/calibration").json()
    assert cal["labelled"] == 2 and cal["misses"] == 1 and cal["points"][-1]["observed_miss_rate"] == 0.5


def test_retention_checks_the_secret_before_touching_the_database():
    from fastapi.testclient import TestClient

    from codetwin_cloud.app import Settings, create_app

    broken = Settings(database_url="postgresql://nobody@127.0.0.1:1/none", cron_secret="s")
    assert TestClient(create_app(broken)).get("/api/cron/retention").status_code == 401


def test_operator_typo_never_connects(monkeypatch, capsys):
    import pytest as _pytest

    from codetwin_cloud.__main__ import main

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with _pytest.raises(SystemExit):
        main(["add-project", "shop"])
    assert "OWNER/NAME" in capsys.readouterr().err


def test_request_ids_are_short_and_plain(client):
    ok = client.get("/api/health", headers={"x-request-id": "ci-run-42"})
    assert ok.headers["x-request-id"] == "ci-run-42"
    long = client.get("/api/health", headers={"x-request-id": "x" * 500})
    assert long.headers["x-request-id"] != "x" * 500 and len(long.headers["x-request-id"]) <= 64


def test_successful_health_probes_are_not_logged(client, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="codetwin_cloud")
    assert client.get("/api/health").status_code == 200
    client.get("/api/v1/projects")
    paths = [json.loads(r.getMessage()).get("path") for r in caplog.records if r.getMessage().startswith("{")]
    assert "/api/health" not in paths and "/api/v1/projects" in paths


def test_failed_health_probes_are_logged(caplog):
    import logging

    from fastapi.testclient import TestClient

    from codetwin_cloud.app import Settings, create_app

    caplog.set_level(logging.INFO, logger="codetwin_cloud")
    broken = Settings(database_url="postgresql://nobody@127.0.0.1:1/none")
    assert TestClient(create_app(broken)).get("/api/health").status_code == 503
    assert any('"/api/health"' in r.getMessage() and '"status": 503' in r.getMessage() for r in caplog.records)


def test_values_carried_by_the_report_match_the_local_api(client, database):
    """A report from a 0.3 client carries alpha_t, test_files and suite_seconds; the cloud shows those, not values
    estimated from the per-test rows (#77). Older reports keep the estimate (test_read_values)."""
    register(database)
    r = report(outcome={"missed": False, "failing": []})
    r["decision"] |= {"alpha_t": 0.08, "test_files": 5, "suite_seconds": 2.5}
    assert client.post("/api/v1/reports", json=r, headers=auth_header(oidc())).status_code in (200, 201)
    base = "/api/v1/projects/acme/shop"
    s = client.get(f"{base}/summary").json()
    assert (s["alpha"], s["alpha_t"], s["test_files"], s["suite_seconds"]) == (0.1, 0.08, 5, 2.5)
    assert client.get(f"{base}/decisions").json()[0]["alpha_t"] == 0.08
    assert client.get(f"{base}/calibration").json()["points"][0]["alpha_t"] == 0.08


def test_an_empty_project_has_no_made_up_target(client, database):
    register(database)
    s = client.get("/api/v1/projects/acme/shop/summary").json()
    assert s["alpha"] is None and s["alpha_t"] is None and s["test_files"] == 0


def test_values_match_the_local_api_on_the_demo_project(client, database):
    """The shared fixture: the local API's answers saved in the dashboard demo snapshot. Upload what `codetwin push`
    would send for its newest decisions, then compare the cloud's answers with the local ones value by value."""
    register(database)
    local_rows = json.loads((DEMO / "decisions__limit-10.json").read_text())[:4]          # newest first
    local_summary = json.loads((DEMO / "summary.json").read_text())
    for i, row in enumerate(reversed(local_rows)):                                        # upload oldest first
        r = report(run={"source": "github-actions", "id": str(2000 + i), "attempt": 1},
                   outcome=None if row["missed"] is None else {"missed": row["missed"], "failing": []})
        r["commit"]["base"] = row["base"]
        r["decision"] = {"decision": row["decision"], "residual_risk": row["residual_risk"], "alpha": row["alpha"],
                         "alpha_t": row["alpha_t"], "threshold": row["threshold"], "mode": row["mode"],
                         "selected": row["selected"], "reasons": row["reasons"],
                         "test_files": local_summary["test_files"], "suite_seconds": local_summary["suite_seconds"]}
        res = client.post("/api/v1/reports", json=r, headers=auth_header(oidc(run_id=str(2000 + i))))
        assert res.status_code == 201, res.json()
    base = "/api/v1/projects/acme/shop"
    cloud_rows = client.get(f"{base}/decisions", params={"limit": 10}).json()
    same = [k for k in local_rows[0] if k not in ("id", "recorded")]                       # ids are per store
    assert [{k: c[k] for k in same} for c in cloud_rows] == [{k: r[k] for k in same} for r in local_rows]
    s = client.get(f"{base}/summary").json()
    for k in ("alpha", "recorded_commit", "test_files", "suite_seconds"):
        assert s[k] == local_summary[k], k


def test_the_upload_lock_holds_the_hourly_limit_under_concurrency(settings, database, monkeypatch):
    """Ten uploads at once against a limit of five: exactly five are stored (the per-project advisory lock).
    The insert is slowed down so that, without the lock, every upload would count the same four or fewer."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException

    from codetwin_cloud import app as cloud_app

    pid = register(database)
    with db.connect(database) as c:      # already bound: uploads take no row lock, only the advisory lock serialises
        c.execute("update project set github_repository_id = 111 where id = %s", (pid,))
    real_insert = cloud_app._insert

    def slow_insert(*args):
        time.sleep(0.2)
        return real_insert(*args)

    monkeypatch.setattr(cloud_app, "_insert", slow_insert)

    def upload(i: int) -> int:
        body = json.dumps(report(run={"source": "github-actions", "id": str(3000 + i), "attempt": 1})).encode()
        try:
            cloud_app._store(body, oidc(run_id=str(3000 + i)), settings)
            return 201
        except HTTPException as e:
            return e.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = sorted(pool.map(upload, range(10)))
    assert codes == [201] * settings.uploads_per_hour + [429] * (10 - settings.uploads_per_hour)
    with db.connect(database) as c:
        assert c.execute("select count(*) as n from report").fetchone()["n"] == settings.uploads_per_hour
