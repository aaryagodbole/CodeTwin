# Releasing

Versions follow [Semantic Versioning](https://semver.org/). `0.x` releases are published as pre-releases.

## Steps

1. On `dev`: move the **Unreleased** entries in `CHANGELOG.md` under a new version heading, and set the same
   version in `src/codetwin/__init__.py` and `extensions/vscode/package.json`.
2. Open a pull request `dev` → `main` and merge it with a **merge commit** (not squash) once CI is green.
3. Start the release, either way:
   - **GitHub website:** Actions → **Release** → **Run workflow** → branch `main`, tag `v0.2.0` → Run.
   - **Terminal:** `git checkout main && git pull && git tag -a v0.2.0 -m "v0.2.0" && git push origin v0.2.0`
4. The **Release** workflow tests, builds, creates the tag (website route) and publishes. If the tag does not
   match the versions, it stops before anything is published.

## What gets published

| Where | What | Needs |
|---|---|---|
| GitHub Releases | `codetwin-X.Y.Z-py3-none-any.whl` (dashboard bundled), sdist, `codetwin-X.Y.Z.vsix`, notes from the changelog | nothing |
| VS Code Marketplace | the extension (pre-release while 0.x) | secret `VSCE_PAT`; `publisher` in `extensions/vscode/package.json` = your publisher ID |
| Open VSX (Cursor, Windsurf, VSCodium) | the extension | secret `OVSX_PAT`; namespace = publisher ID |
| PyPI | the Python package | variable `PUBLISH_PYPI=true`, environment `pypi`, PyPI trusted publisher for `release.yml` |

## One-time setup of the stores

- **VS Code Marketplace:** create a publisher at marketplace.visualstudio.com/manage, create an Azure DevOps
  personal access token with the *Marketplace → Manage* scope, and save it as repository secret `VSCE_PAT`.
- **Open VSX:** sign in at open-vsx.org, sign the publisher agreement, create the namespace
  (`npx ovsx create-namespace <publisher> -p <token>`), and save the token as secret `OVSX_PAT`.
- **PyPI:** on pypi.org add a pending trusted publisher (owner and repository of this repo, workflow
  `release.yml`, environment `pypi`), create the `pypi` environment in the repository settings, and set the
  repository variable `PUBLISH_PYPI` to `true`.

## Install a release without the stores

```bash
pip install "codetwin[server] @ https://github.com/<owner>/<repo>/releases/download/vX.Y.Z/codetwin-X.Y.Z-py3-none-any.whl"
code --install-extension codetwin-X.Y.Z.vsix
```
(The repository is private: download the files from the release page while signed in.)
