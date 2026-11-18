"""`codetwin push`: what a report contains (and never contains), and how it is sent."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from codetwin import push, report
from codetwin.cli import main
from codetwin.engine import Engine


def _decide(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    main(["-C", str(toy_repo), "select", "--json"])
    return json.loads(capsys.readouterr().out)


def test_report_holds_ids_and_numbers_never_code(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    decision = _decide(toy_repo, capsys)
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env={}, repository="acme/shop")
    assert body["schema"] == "codetwin.report/v1" and body["repository"] == "acme/shop"
    assert body["run"]["source"] == "cli" and body["run"]["id"].startswith("cli-") and body["run"]["attempt"] == 1
    assert set(body["decision"]["sections"]) <= report.publishable()
    assert {"contracts", "cross_repo"}.isdisjoint(body["decision"]["sections"])   # not opted in
    ids = {t["id"] for t in body["decision"]["tests"]}
    assert set(body["decision"]["selected"]) <= ids and all(t["score"] is not None for t in body["decision"]["tests"])
    text = json.dumps(body)
    for f in ["src/shop/price.py", "tests/test_price.py"]:          # no line of any source or test file
        for line in (toy_repo / f).read_text().splitlines():
            if len(line.strip()) > 12:
                assert line.strip() not in text, line


def test_github_actions_identity_comes_from_the_environment(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 63}}))
    env = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "777", "GITHUB_RUN_ATTEMPT": "2",
           "GITHUB_REPOSITORY": "acme/shop", "GITHUB_REF": "refs/pull/63/merge", "GITHUB_EVENT_PATH": str(event)}
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env=env)
    assert body["run"] == {"source": "github-actions", "id": "777", "attempt": 2}
    assert body["commit"]["head"] == "c" * 40 and body["commit"]["pull_request"] == 63


def test_dry_run_prints_and_sends_nothing(toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision))
    assert main(["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]) == 0
    assert json.loads(capsys.readouterr().out)["decision"]["decision"] == decision["decision"]


def test_https_only_except_localhost() -> None:
    assert push.check_server("https://api.example.com/") == "https://api.example.com"
    assert push.check_server("http://localhost:8080") == "http://localhost:8080"
    for bad in ["http://api.example.com", "ftp://x", "file:///etc/passwd"]:
        with pytest.raises(push.PushError):
            push.check_server(bad)


class _Server:
    """A local HTTP server recording requests; answers with a fixed status and JSON body."""

    def __init__(self, status=201, body=b'{"id": 5, "created": true}'):
        seen = self.seen = []

        class H(BaseHTTPRequestHandler):
            def _reply(self):
                n = int(self.headers.get("content-length") or 0)
                seen.append((self.command, self.path, dict(self.headers), self.rfile.read(n)))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _reply

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://localhost:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def test_send_posts_json_with_the_token() -> None:
    srv = _Server()
    try:
        res = push.send(srv.url, {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        srv.close()
    method, path, headers, body = srv.seen[0]
    assert (method, path, res) == ("POST", "/api/v1/reports", {"status": 201, "id": 5, "created": True})
    assert headers["Authorization"] == "Bearer ctp_abc" and json.loads(body) == {"schema": "codetwin.report/v1"}


def test_refused_upload_fails_unless_best_effort(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision))
    srv = _Server(status=403, body=b'{"detail": "not registered"}')
    try:
        base = ["-C", str(toy_repo), "push", "--decision", str(f), "--server", srv.url, "--token", "ctp_x",
                "--repository", "acme/shop"]
        assert main(base) == 1
        assert main([*base, "--best-effort"]) == 0
    finally:
        srv.close()
    assert "upload refused (403)" in capsys.readouterr().err


def test_github_oidc_token_is_requested_with_our_audience() -> None:
    srv = _Server(status=200, body=b'{"value": "jwt.from.github"}')
    try:
        tok = push.github_oidc_token({"ACTIONS_ID_TOKEN_REQUEST_URL": f"{srv.url}/token?x=1",
                                      "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "req-token"})
    finally:
        srv.close()
    _, path, headers, _ = srv.seen[0]
    assert tok == "jwt.from.github" and path == "/token?x=1&audience=codetwin-cloud"
    assert headers["Authorization"] == "bearer req-token"
    with pytest.raises(push.PushError, match="id-token: write"):
        push.github_oidc_token({})


def test_cli_run_id_follows_the_decision_not_the_local_database(
    toy_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two clones both have decision 1; different decisions must not share a run id (the cloud dedups on it)."""
    decision = _decide(toy_repo, capsys)
    other = {**decision, "decision": "abstain" if decision["decision"] == "proceed" else "proceed"}
    with Engine(toy_repo) as eng:
        a = push.build_report(eng, decision, env={}, repository="acme/shop")["run"]["id"]
        again = push.build_report(eng, decision, env={}, repository="acme/shop")["run"]["id"]
        b = push.build_report(eng, other, env={}, repository="acme/shop")["run"]["id"]
    assert a == again and a != b


def test_scores_come_only_from_the_same_stored_decision(toy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A different decision that selects the same tests must not get the stored decision's scores and alpha."""
    decision = _decide(toy_repo, capsys)
    other = {**decision, "mode": "fallback"}
    with Engine(toy_repo) as eng:
        same = push.build_report(eng, decision, env={}, repository="acme/shop")["decision"]
        diff = push.build_report(eng, other, env={}, repository="acme/shop")["decision"]
    assert any(t["score"] is not None for t in same["tests"])
    assert diff["alpha"] is None and all(t["score"] is None for t in diff["tests"])


def test_malformed_decision_json_is_a_push_error(
    toy_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    decision = _decide(toy_repo, capsys)
    for bad in [{**decision, "selected": None}, {**decision, "residual_risk": "high"}, [1, 2]]:
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(bad), encoding="utf-8")
        base = ["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]
        assert main(base) == 1
        assert main([*base, "--best-effort"]) == 0
        assert "codetwin push" in capsys.readouterr().err


@pytest.mark.parametrize("body", [b"null", b"[]", b'{"id": "x", "created": true}'])
def test_unexpected_upload_answers_are_push_errors(body: bytes) -> None:
    srv = _Server(status=200, body=body)
    try:
        with pytest.raises(push.PushError):
            push.send(srv.url, {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        srv.close()


def test_a_truncated_answer_is_a_push_error() -> None:
    """The server promises more bytes than it sends (http.client.IncompleteRead is not an OSError)."""
    class Short(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length") or 0))
            self.send_response(201)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b'{"id": 1')

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Short)
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    try:
        with pytest.raises(push.PushError):
            push.send(f"http://localhost:{httpd.server_port}", {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        httpd.server_close()


def test_redirects_are_not_followed_with_the_token() -> None:
    """A redirect could send the bearer token over plain HTTP or to another origin."""
    target = _Server()
    redirect = _Server(status=302, body=b"")
    redirect_to = f"{target.url}/elsewhere"

    class R(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length") or 0))
            self.send_response(302)
            self.send_header("Location", redirect_to)
            self.end_headers()

        def log_message(self, *a):
            pass

    redirect.close()
    httpd = HTTPServer(("127.0.0.1", 0), R)
    threading.Thread(target=httpd.handle_request, daemon=True).start()
    try:
        with pytest.raises(push.PushError, match="redirect"):
            push.send(f"http://localhost:{httpd.server_port}", {"schema": "codetwin.report/v1"}, "ctp_secret")
    finally:
        httpd.server_close()
        target.close()
    assert not target.seen, "the token followed the redirect"
