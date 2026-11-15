"""Contract diff: OpenAPI and JSON-schema breaking changes, path/field matching, consumers and tests."""
import json
import subprocess
import textwrap

import yaml

from codetwin.cli import main
from codetwin.contracts.diff import diff_documents
from codetwin.contracts.link import field_regex, path_regex

OLD = yaml.safe_load(textwrap.dedent("""\
    openapi: 3.0.0
    paths:
      /users/{id}:
        parameters:
          - {name: id, in: path, required: true, schema: {type: integer}}
        get:
          parameters:
            - {name: verbose, in: query, schema: {type: boolean}}
          responses:
            200:
              content: {application/json: {schema: {$ref: '#/components/schemas/User'}}}
            404: {description: missing}
        delete:
          responses: {204: {description: gone}}
      /health:
        get: {responses: {200: {description: ok}}}
    components:
      schemas:
        User:
          type: object
          required: [id]
          properties:
            id: {type: integer}
            email: {type: string}
            role: {type: string, enum: [admin, user, guest]}
            age: {type: integer}
    """))


def _new():
    new = json.loads(json.dumps(OLD))
    del new["paths"]["/health"]
    del new["paths"]["/users/{id}"]["delete"]
    new["paths"]["/users/{id}"]["get"]["parameters"] = [{"name": "fields", "in": "query", "required": True,
                                                         "schema": {"type": "string"}}]
    del new["paths"]["/users/{id}"]["get"]["responses"]["404"]   # JSON keys are strings
    u = new["components"]["schemas"]["User"]
    del u["properties"]["email"]
    u["properties"]["role"]["enum"] = ["admin", "user"]
    u["properties"]["age"]["type"] = "string"
    u["required"] = ["id", "role"]
    u["properties"]["nick"] = {"type": "string"}
    return new


def test_openapi_breaking_changes():
    ch = {(c.kind, c.location) for c in diff_documents(OLD, _new(), "api.yaml") if c.breaking}
    assert ("path-removed", "/health") in ch
    assert ("operation-removed", "DELETE /users/{id}") in ch
    assert ("parameter-removed", "GET /users/{id} query verbose") in ch
    assert ("parameter-required", "GET /users/{id} query fields") in ch
    assert ("response-removed", "GET /users/{id} 404") in ch
    assert ("property-removed", "User.email") in ch
    assert ("enum-value-removed", "User.role") in ch
    assert ("type-changed", "User.age") in ch
    assert ("property-required", "User.role") in ch
    non = {(c.kind, c.location) for c in diff_documents(OLD, _new(), "api.yaml") if not c.breaking}
    assert ("property-added", "User.nick") in non
    assert diff_documents(OLD, OLD, "api.yaml") == []


def test_json_schema():
    old = {"title": "Order", "type": "object", "properties": {"id": {"type": "string"},
                                                              "lines": {"type": "array", "items": {"type": "object",
                                                                        "properties": {"sku": {"type": "string"}}}}}}
    new = {"title": "Order", "type": "object", "required": ["id"],
           "properties": {"id": {"type": "string"}, "lines": {"type": "array", "items": {"type": "object", "properties": {}}}}}
    ch = {(c.kind, c.location) for c in diff_documents(old, new, "order.schema.json") if c.breaking}
    assert ch == {("property-required", "Order.id"), ("property-removed", "Order.lines[].sku")}


def test_matching():
    rx = path_regex("/users/{id}/orders")
    assert rx.search('fetch("/users/42/orders")') and rx.search("get(`/users/${id}/orders`)")
    assert not rx.search('"/users/42/orders-old"')
    assert path_regex("/health").search("requests.get(base + '/health')")
    assert path_regex("/users/{id}").search('url = "/users/" + uid')
    f = field_regex("email")
    for ok in ('u["email"]', "user.email", "{ email: x }", "email = x"):
        assert f.search(ok), ok
    for bad in ("send_email(x)", "emails", "a == email"):
        assert not f.search(bad), bad


def test_end_to_end_with_dependent(toy_repo, tmp_path, capsys):
    (toy_repo / "openapi.yaml").write_text(yaml.safe_dump(OLD))
    (toy_repo / "src/shop/client.py").write_text('def health(base):\n    return base + "/health"\n')
    subprocess.run(["git", "add", "-A"], cwd=toy_repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "api"], cwd=toy_repo, check=True)
    web = tmp_path / "web"
    (web / "web").mkdir(parents=True)
    (web / "tests").mkdir()
    (web / "web" / "__init__.py").write_text("")
    (web / "web" / "profile.py").write_text('def mail(user):\n    return user["email"]\n')
    (web / "tests" / "test_profile.py").write_text("from web.profile import mail\n\ndef test_mail():\n    assert mail({'email': 'a'})\n")
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "i"]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=web, check=True)
    main(["-C", str(web), "init"])
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "web"\npath = "{web.as_posix()}"\n')
    (toy_repo / "openapi.yaml").write_text(yaml.safe_dump(_new()))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "contracts", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["files"] == ["openapi.yaml"]
    by = {b["location"]: b for b in out["breaking"]}
    assert {"repo": "this repository", "file": "src/shop/client.py", "line": 2, "how": "path-literal"} \
        in by["/health"]["consumers"]
    email = by["User.email"]
    assert any(c["repo"] == "web" and c["file"] == "web/profile.py" for c in email["consumers"])
    assert "web:tests/test_profile.py" in email["tests"]
    assert any("DELETE /users/{id}" in u for u in out["unknowns"])     # nothing found is unknown, not "safe"
    assert main(["-C", str(toy_repo), "contracts", "--fail-on-breaking"]) == 1

    from codetwin.engine import Engine
    from codetwin.store.analyses import api_history, breaking_matrix
    with Engine(toy_repo) as eng:
        st = eng.store
        # the second run reused the stored contents and their diff (content-addressed, computed once)
        assert st.con.execute("select count(*) from contract_version").fetchone()[0] == 2
        assert st.con.execute("select count(*) from contract_diff").fetchone()[0] == 1
        assert [h["sha"] for h in api_history(st, "openapi.yaml")][-1] == "working-tree"
        levels = dict(st.con.execute("select level, count(*) from contract_change group by level"))
        assert levels["error"] == len(out["breaking"]) and levels.get("info", 0) == \
            len(out["changes"]) - len(out["breaking"])
        m = {(r["location"], r["repository"]): r for r in breaking_matrix(st, out["analysis_id"])}
        assert m[("User.email", "web")]["state"] == "affected" and m[("User.email", "web")]["tests"] >= 1
        assert m[("/health", ".")]["state"] == "affected" and m[("/health", "web")]["state"] == "clear"
        assert m[("DELETE /users/{id}", "web")]["state"] == "clear"
        kinds = dict(st.con.execute("select location, kind from api_element"))
        assert kinds["/health"] == "path" and kinds["User.email"] == "property" and kinds["DELETE /users/{id}"] == \
            "operation"
        rel = set(st.con.execute("select source, type, target from repository_relation"))
        assert {(".", "providesApi", "openapi.yaml"), ("web", "consumesApi", "openapi.yaml")} <= rel
        assert st.con.execute("pragma foreign_key_check").fetchall() == []

# ------------------------------------------------------------------ review fixes (PR #40)
def test_path_matching_is_exact():
    assert not path_regex("/health").search('get("/health/status")')
    assert not path_regex("/health").search('get("/health.json")')
    assert path_regex("/health").search('get("/health?verbose=1")')
    orders = path_regex("/users/{id}/orders")
    assert orders.search('url = "/users/" + uid + "/orders"')
    assert not orders.search('url = "/users/" + uid + "/profiles"')


def test_openapi2_body_schema_is_diffed():
    def doc(props):
        return {"swagger": "2.0", "paths": {"/users": {"post": {
            "parameters": [{"name": "user", "in": "body", "schema": {"$ref": "#/definitions/NewUser"}}],
            "responses": {"201": {"description": "ok"}}}}},
            "definitions": {"NewUser": {"type": "object", "properties": props}}}
    old, new = doc({"name": {"type": "string"}, "email": {"type": "string"}}), doc({"name": {"type": "string"}})
    ch = {(c.kind, c.location) for c in diff_documents(old, new, "swagger.json") if c.breaking}
    assert ("property-removed", "POST /users request.email") in ch


def test_deleted_and_renamed_contract_files(toy_repo, capsys):
    (toy_repo / "openapi.yaml").write_text(yaml.safe_dump(OLD))
    (toy_repo / "order.schema.json").write_text(json.dumps({"title": "Order", "type": "object"}))
    for cmd in (["add", "-A"], ["commit", "-qm", "api"]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=toy_repo, check=True)
    main(["-C", str(toy_repo), "init"])
    (toy_repo / "api").mkdir()
    subprocess.run(["git", "mv", "openapi.yaml", "api/openapi.yaml"], cwd=toy_repo, check=True, capture_output=True)
    (toy_repo / "order.schema.json").unlink()
    capsys.readouterr()
    main(["-C", str(toy_repo), "contracts", "--json", "--base", "HEAD"])
    out = json.loads(capsys.readouterr().out)
    locs = {b["location"] for b in out["breaking"]}
    assert "Order" in locs                                           # deleted schema file: breaking
    assert not any(b["file"].endswith("openapi.yaml") for b in out["breaking"])   # renamed, unchanged: nothing


def test_untracked_move_is_not_a_deletion(toy_repo, capsys):
    (toy_repo / "openapi.yaml").write_text(yaml.safe_dump(OLD))
    for cmd in (["add", "-A"], ["commit", "-qm", "api"]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=toy_repo, check=True)
    main(["-C", str(toy_repo), "init"])
    (toy_repo / "docs").mkdir()
    (toy_repo / "openapi.yaml").rename(toy_repo / "docs" / "openapi.yaml")
    capsys.readouterr()
    main(["-C", str(toy_repo), "contracts", "--json", "--base", "HEAD"])
    assert json.loads(capsys.readouterr().out)["breaking"] == []
