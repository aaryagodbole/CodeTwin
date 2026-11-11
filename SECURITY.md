# Security policy

## Reporting a vulnerability

Do not open a public issue. Use **Security → Report a vulnerability** (private vulnerability reporting) in
this repository, or contact the maintainers listed in `.github/CODEOWNERS`. Expect an answer within 7 days.

## What CodeTwin runs

CodeTwin runs the analysed project's test suite (`pytest`) and `git` on the machine where it is invoked.
Only run it on code you trust, as you would `pytest` itself. The VS Code extension is disabled in untrusted
workspaces, and the path of the CLI can only be set in user or machine settings, not by a repository.
`codetwin serve` listens on 127.0.0.1 by default and only reads the local evidence store.

## Supported versions

Only the latest release receives fixes while the project is in `0.x`.
