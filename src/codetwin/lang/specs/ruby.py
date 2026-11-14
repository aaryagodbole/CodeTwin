"""Ruby: RSpec or Minitest, coverage from Ruby's built-in `Coverage` module (no gem needed), as LCOV.

`require_relative` and `require` of files under `lib/` resolve to files. `send`, `public_send`,
`const_get`, `instance_variable_get`, `eval` and `method_missing` are reported as dynamic.
"""
from __future__ import annotations

import posixpath
from pathlib import Path

from ..spec import Runner, Spec
from ._util import first_arg, rel_join, string_value, txt

DYNAMIC = {"send", "public_send", "__send__", "const_get", "instance_variable_get", "eval", "instance_eval",
           "class_eval", "define_method", "method_missing"}
HELPER = str(Path(__file__).with_name("_ruby_coverage.rb"))


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "call":
        m = n.child_by_field_name("method")
        name = txt(m, src) if m is not None else ""
        if name in ("require", "require_relative", "load"):
            s = string_value(first_arg(n, src), src)
            return [f"{name}:{s}"] if s else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type in ("call", "method"):
        m = n.child_by_field_name("method") or n.child_by_field_name("name")
        name = txt(m, src) if m is not None else ""
        if name in DYNAMIC:
            return name
    return None


def resolve(spec: str, from_file: str, idx) -> list[str]:
    kind, _, path = spec.partition(":")
    path = path if path.endswith(".rb") else path + ".rb"
    cands = [rel_join(from_file, path)] if kind == "require_relative" else \
        [posixpath.join(d, path) for d in ("lib", "app", "", "spec", "test")] + [rel_join(from_file, path)]
    for c in cands:
        c = posixpath.normpath(c)
        if c in idx.files:
            return [c]
    return []


RUNNERS = [
    Runner("rspec", f"bundle exec ruby -r{HELPER} -S rspec {{test}}", "lcov", "lcov.info",
           run_command="bundle exec rspec {test}", env={"CODETWIN_COV_DIR": "{cov_dir}"},
           detect=lambda root: (root / ".rspec").exists() or (root / "spec").is_dir()),
    Runner("minitest", f"bundle exec ruby -r{HELPER} -Ilib -Itest {{test}}", "lcov", "lcov.info",
           run_command="bundle exec ruby -Ilib -Itest {test}", env={"CODETWIN_COV_DIR": "{cov_dir}"},
           detect=lambda root: (root / "test").is_dir()),
]

SPEC = Spec(
    name="ruby",
    grammars={".rb": "ruby"},
    test_globs=["*_spec.rb", "test_*.rb", "*_test.rb"],
    markers=["Gemfile", "Rakefile"],
    source_dirs=["lib", "app"],
    tests_dirs=["spec", "test"],
    function_types={"method", "singleton_method", "lambda", "block", "do_block"},
    decl_types={"method", "singleton_method", "comment"},
    imports=imports, dynamic=dynamic, resolve=resolve, runners=RUNNERS,
)
