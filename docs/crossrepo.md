# Connected repositories

CodeTwin can follow a change in this repository into the repositories that use it. Declare as many as you need
in `.codetwin.toml`, each one either a local folder (`path`) or a git URL (`url`):

```toml
[[repos]]
name = "web"
url = "https://github.com/acme/web.git"      # cloned into .codetwin/repos/web
# ref = "main"                               # optional: branch or tag (default: the remote's default branch)

[[repos]]
name = "mobile"
url = "git@github.com:acme/mobile.git"       # ssh works too

[[repos]]
name = "admin"
path = "../admin"                            # a checkout next to this one, relative to this repository
# packages = ["@acme/core"]                  # optional, any entry: how it imports this repository

[crossrepo]
# packages = ["@acme/core"]      # optional: this repository's package names (default: detected)
```

**URL entries.** `codetwin repos --sync` (or `codetwin crossrepo --sync`) clones each one, one commit deep, into
`.codetwin/repos/<name>`, and updates it on later runs. Analysis itself never uses the network: `select`, the
review and the MCP tools read the local copy, and an entry that was never synced is an unknown that says to run
`--sync`. The GitHub Action syncs before selecting (`sync-repos`, on by default). `codetwin repos` lists every
entry with where its files are and whether they are ready.

- Accepted URLs: `https://`, `ssh://`, `user@host:path` and `file://`. Anything else (for example git's `ext::`
  transport) is refused.
- Never put a password or token in the URL; such a URL is refused. An `https://` URL may not carry a user name
  at all (a token is often given as one); an ssh URL may name a user but not a password. Private repositories use
  git's own credentials: a credential helper, an SSH key, or in Actions a token configured for that host.
- Each entry needs a unique `name` (default: the last part of the URL or path; compared without case, since it
  names a folder), and either `path` or `url`, not both. An entry that breaks a rule is reported as `invalid` with
  the reason; it is never skipped silently.
- `--sync` never leaves a half-cloned folder behind, and a failed update (network, credentials) keeps the last good
  copy. The GitHub Action does not sync for pull requests from forks: their `.codetwin.toml` could name any URL.

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
