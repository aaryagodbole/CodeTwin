"""`codetwin push`: what a report contains (and never contains), and how it is sent."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from codetwin import push, report
from codetwin.cli import main
from codetwin.engine import Engine


def _decide(toy_repo, capsys) -> dict:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    main(["-C", str(toy_repo), "select", "--json"])
    return json.loads(capsys.readouterr().out)


def test_report_holds_ids_and_numbers_never_code(toy_repo, capsys):
    decision = _decide(toy_repo, capsys)
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env={}, repository="acme/shop")
    assert body["schema"] == "codetwin.report/v1" and body["repository"] == "acme/shop"
    assert body["run"] == {"source": "cli", "id": "cli-1", "attempt": 1}
    assert set(body["decision"]["sections"]) <= report.publishable()
    assert {"contracts", "cross_repo"}.isdisjoint(body["decision"]["sections"])   # not opted in
    ids = {t["id"] for t in body["decision"]["tests"]}
    assert set(body["decision"]["selected"]) <= ids and all(t["score"] is not None for t in body["decision"]["tests"])
    text = json.dumps(body)
    for f in ["src/shop/price.py", "tests/test_price.py"]:          # no line of any source or test file
        for line in (toy_repo / f).read_text().splitlines():
            if len(line.strip()) > 12:
                assert line.strip() not in text, line


def test_github_actions_identity_comes_from_the_environment(toy_repo, capsys, tmp_path):
    decision = _decide(toy_repo, capsys)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 63}}))
    env = {"GITHUB_ACTIONS": "true", "GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": "777", "GITHUB_RUN_ATTEMPT": "2",
           "GITHUB_REPOSITORY": "acme/shop", "GITHUB_REF": "refs/pull/63/merge", "GITHUB_EVENT_PATH": str(event)}
    with Engine(toy_repo) as eng:
        body = push.build_report(eng, decision, env=env)
    assert body["run"] == {"source": "github-actions", "id": "777", "attempt": 2}
    assert body["commit"]["head"] == "c" * 40 and body["commit"]["pull_request"] == 63


def test_dry_run_prints_and_sends_nothing(toy_repo, capsys, tmp_path):
    decision = _decide(toy_repo, capsys)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decision))
    assert main(["-C", str(toy_repo), "push", "--decision", str(f), "--dry-run", "--repository", "acme/shop"]) == 0
    assert json.loads(capsys.readouterr().out)["decision"]["decision"] == decision["decision"]


def test_https_only_except_localhost():
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


def test_send_posts_json_with_the_token():
    srv = _Server()
    try:
        res = push.send(srv.url, {"schema": "codetwin.report/v1"}, "ctp_abc")
    finally:
        srv.close()
    method, path, headers, body = srv.seen[0]
    assert (method, path, res) == ("POST", "/api/v1/reports", {"status": 201, "id": 5, "created": True})
    assert headers["Authorization"] == "Bearer ctp_abc" and json.loads(body) == {"schema": "codetwin.report/v1"}


def test_refused_upload_fails_unless_best_effort(toy_repo, capsys, tmp_path):
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


def test_github_oidc_token_is_requested_with_our_audience():
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
