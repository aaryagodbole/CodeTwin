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
        names = [r["name"] for r in c.execute("select name from schema_migrations").fetchall()]
    assert names == ["0001_initial.sql"]
