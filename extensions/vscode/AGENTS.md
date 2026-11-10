# AGENTS.md (VS Code extension)

- Build: `npm install && npm run compile` (TypeScript, strict mode). Debug: open this folder in VS Code and press F5.
- The extension only calls the `codetwin` CLI (`src/cli.ts`) and parses its `--json` output; never re-implement
  analysis here. If the extension needs new data, add it to the CLI first, with a test in `tests/`.
- Keep `Decision` in `src/cli.ts` in sync with `_print_decision` in `src/codetwin/cli.py`.
- Planned features and their order are in `docs/roadmap.md` (select-to-impact panel first).
