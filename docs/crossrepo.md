# Connected repositories

CodeTwin can follow a change in this repository into the repositories that use it. Declare them in
`.codetwin.toml`:

```toml
[[repos]]
name = "web"
path = "../web"                  # relative to this repository
# packages = ["@acme/core"]      # optional: how web imports this repository

[crossrepo]
# packages = ["@acme/core"]      # optional: this repository's package names (default: detected)
```

**Package names** are detected from build files: Python top-level packages, `package.json` `name`, the `go.mod`
module path, the `Cargo.toml` crate, Java/Kotlin package and C# namespace prefixes, gemspec names and
`composer.json` PSR-4 namespaces.

**Consumers.** In each dependent, a file that imports one of those names is a consumer. If it also names a changed
function, method or class, the link is `uses-changed-symbol` (with the lines); otherwise `imports-package`.

**Tests.** If the dependent has its own recorded run (`codetwin record` there), tests come from its per-test
coverage (`runtime`); otherwise from its static import graph (`static`). Test files that import this repository
directly are listed as `direct:*`.

**Unknowns** are never dropped: a missing repository, an unknown package name, an unsupported language, files
that use dynamic imports, no recorded run, or a consumer of a changed symbol that no test executes.

Commands: `codetwin crossrepo [--base REF] [--json]`, the `cross_repo` section of `codetwin select --json`
(listed in the GitHub Action's job summary), and the MCP tool `get_cross_repo_impact`. Every language with an adapter works on both
sides; the two repositories may use different languages.
