# Languages

CodeTwin's method (risk ranking, residual risk r(c) and q(c), conformal calibration, adaptive calibration,
abstention, no-op and weak-check evidence) does not depend on the programming language. It reads two things
per project: **which test file executed which lines** (and how long it took and whether it failed) and
**static facts** of every file (dependencies, dynamic constructs, function spans, load-time code). A language
adapter produces those two.

CodeTwin works on **any repository**: one language, several languages at once (a Python service with a
TypeScript front end and a Go tool), or a language it has never seen.

| Language | Static facts | Test runner presets (detected per project folder) | Coverage | Weakcheck mutants |
|---|---|---|---|---|
| Python | `ast` | pytest | coverage.py contexts | yes |
| JavaScript / TypeScript | tree-sitter | Vitest, Jest, Mocha, `node --test`, any `npm test` | LCOV | yes |
| Go | tree-sitter | `go test` (per test file, its `Test*` functions) | `-coverprofile` | yes |
| Java | tree-sitter | Maven + Surefire, Gradle (JaCoCo applied automatically) | JaCoCo XML | yes |
| Kotlin | tree-sitter | Maven, Gradle (as Java) | JaCoCo XML | yes |
| C# | tree-sitter | `dotnet test` + coverlet | Cobertura | yes |
| Rust | tree-sitter | `cargo llvm-cov` (integration test files and `#[cfg(test)]` modules) | LCOV | yes |
| Ruby | tree-sitter | RSpec, Minitest (built-in `Coverage`, no gem), with or without Bundler | LCOV | yes |
| PHP | tree-sitter | PHPUnit (Xdebug or PCOV) | Clover | yes |
| C / C++ | tree-sitter | none: set `test_command` | LCOV, Cobertura | yes |
| **any other language** | tree-sitter grammar (300+), rules built automatically | none: set `test_command` | any of the five formats | no |

Every row except Kotlin has a sample project in `examples/`, and the `languages` CI job runs **every
feature** on each of them with the language's real toolchain (`scripts/language_smoke.py`): init, record,
select, impact, graph, weakcheck, run, explain, learn and no-op detection. Two more samples cover a language
without a spec or runner (`examples/lua`) and a mixed repository (`examples/mixed`).

Static facts are dependency resolution (imports to files), dynamic constructs the analysis cannot follow
(reported as unknowns, never as "no dependency"), function spans and load-time code. Grammars are downloaded
on first use and cached.

## How a repository is read

- **Languages**: `codetwin init` lists every language that has both source and test files (sample and fixture
  folders such as `examples/`, `testdata/`, `docs/` do not count). One language gives `language = "go"`;
  several give `languages = ["python", "javascript"]` with a `[lang.<name>]` table each.
- **Project folders**: each test runs from the nearest folder above it with a build file of its language
  (`web/package.json`, `services/api/go.mod`, a Maven module), with that folder's test runner. Monorepos work
  without configuration.
- **Python inside a larger repository**: without a `packages` list, import roots are found from the package
  folders (`backend/src` for `backend/src/shop/__init__.py`) and tests are found anywhere.
- **No test runner** (an unknown language, or a runner CodeTwin has no preset for): CodeTwin keeps working on
  static evidence. Impact, graph, no-op detection and selection work; every decision on such a file abstains
  and says that coverage is missing, `learn` refuses to guess, and `run` explains what to configure.

## Setup

```bash
codetwin init                  # detects the language and the test runner; or: codetwin init --language go
codetwin record
```

`codetwin init` writes for example:

```toml
[project]
language = "javascript"
source_dirs = ["src"]
tests_dir = "test"

[runner]
# Detected test runner: vitest.
```

## Any test runner: `[runner]`

Every test file runs on its own with coverage. A preset fills in the commands; override any part, or describe
a runner CodeTwin has no preset for:

```toml
[runner]
test_command = "npx vitest run --coverage.enabled --coverage.reporter=lcov --coverage.reportsDirectory={cov_dir} {test}"
coverage_format = "lcov"         # lcov | gocover | jacoco | cobertura | clover
coverage_file = "lcov.info"      # glob under {cov_dir}; "./target/**/report.xml" for a tool that ignores {cov_dir}
run_command = "npx vitest run {test}"      # without coverage, for weakcheck
setup_command = ""               # once before a recorded run (install, compile)
build_command = ""               # weakcheck: does a mutated copy still compile?
result_glob = ""                 # JUnit XML written by the run; otherwise the exit code decides pass/fail
test_globs = ["**/*.test.ts"]
workers = 1                      # test files run in parallel
timeout = 600                    # seconds per test file
env = { MY_VAR = "{cov_dir}" }   # extra environment variables
```

Placeholders: `{test}` (test file), `{cov_dir}` (empty folder for the report), `{test_dir}`, `{test_stem}`, and
preset-specific ones such as `{test_class}` (JUnit, .NET) or `{names}` (Go test functions). Commands run without
a shell; wrap them in `sh -c "..."` if you need one.

Example for C++ with CMake, GoogleTest and gcovr (one test source file per test binary):

```toml
[project]
language = "cpp"
source_dirs = ["src"]
tests_dir = "tests"

[runner]
setup_command = "cmake --build build"
test_command = "sh -c 'find build -name \"*.gcda\" -delete; ./build/{test_stem} && gcovr -r . --lcov {cov_dir}/lcov.info'"
coverage_format = "lcov"
```

## A language with no spec file

Any language with a tree-sitter grammar works with coverage evidence alone:

```toml
[project]
language = "lua"
source_dirs = ["src"]
tests_dir = "spec"

[language]
grammar = "lua"
extensions = [".lua"]
test_globs = ["*_spec.lua"]
function_types = ["function_declaration"]     # optional: function-level features

[runner]
test_command = "busted --coverage {test}"
coverage_format = "lcov"
```

Without import rules the static graph is empty, so selection relies on coverage, and the decision's unknowns
say that a changed file has no static evidence. To add full support, add `src/codetwin/lang/specs/<name>.py`
with `SPEC = Spec(...)` (see `javascript.py` or `go.py`); it is discovered automatically.

## Mixed repositories

```toml
[project]
languages = ["python", "javascript"]

[lang.python]
source_dirs = ["backend"]        # src_root / packages optional: import roots are found automatically
tests_dir = "backend/tests"

[lang.javascript]
source_dirs = ["web/src"]
tests_dir = "web/test"

[lang.javascript.runner]         # optional, like [runner] for a single language
workers = 2
```

## Limits

- Coverage is per test **file** (per test class for JUnit and .NET), as in the Python study. Projects whose test
  files cannot run on their own need a `test_command` that can.
- Running every test file separately is slower than one suite run; use `workers` for parallel runs.
- Calls between languages (a TypeScript client calling a Python API over HTTP) are invisible to every parser;
  coverage and co-change history still link them when the same tests exercise both.
- The paper's numbers come from the Python study; numbers for other languages come from separate runs.
