# Languages

CodeTwin's method (risk ranking, residual risk r(c) and q(c), conformal calibration, adaptive calibration,
abstention, no-op and weak-check evidence) does not depend on the programming language. It reads two things
per project: **which test file executed which lines** (and how long it took and whether it failed) and
**static facts** of every file (dependencies, dynamic constructs, function spans, load-time code). A language
adapter produces those two.

| Language | Static facts | Test runner presets (detected) | Coverage | Weakcheck mutants | Verified here |
|---|---|---|---|---|---|
| Python | `ast` | pytest | coverage.py contexts | yes | study v3 (8 projects) |
| JavaScript / TypeScript | tree-sitter | Vitest, Jest, Mocha, `node --test`, any `npm test` | LCOV | yes | end-to-end test |
| Go | tree-sitter | `go test` (per test file, its `Test*` functions) | `-coverprofile` | yes | end-to-end test |
| Java | tree-sitter | Maven + Surefire, Gradle (JaCoCo applied automatically) | JaCoCo XML | yes | static facts, JaCoCo reader, mutants |
| Kotlin | tree-sitter | Maven, Gradle (as Java) | JaCoCo XML | no | static facts |
| Rust | tree-sitter | `cargo llvm-cov` (integration test files and `#[cfg(test)]` modules) | LCOV | no | static facts |
| C# | tree-sitter | `dotnet test` + coverlet | Cobertura | no | static facts |
| Ruby | tree-sitter | RSpec, Minitest (built-in `Coverage`, no gem) | LCOV | no | static facts |
| PHP | tree-sitter | PHPUnit (Xdebug or PCOV) | Clover | no | static facts |
| C / C++ | tree-sitter | none: set `test_command` | LCOV, Cobertura | no | static facts |
| any other | tree-sitter grammar (300+) | none: set `test_command` | any of the five formats | no | – |

"Static facts" are dependency resolution (imports to files), dynamic constructs that the analysis cannot follow
(reported as unknowns, never as "no dependency"), function spans and load-time code. Install the tree-sitter
grammars with `pip install "codetwin[languages]"`; grammars are downloaded on first use and cached.

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
coverage_file = "lcov.info"      # glob under {cov_dir}
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

## Limits

- Coverage is per test **file** (per test class for JUnit and .NET), as in the Python study. Projects whose test
  files cannot run on their own need a `test_command` that can.
- Running every test file separately is slower than one suite run; use `workers` for parallel runs.
- The paper's numbers come from Python projects and from the multi-language study in `pilot/v4` (see the paper).
  Presets marked "static facts" above are tested for their parsing and resolution, not on real projects here.
