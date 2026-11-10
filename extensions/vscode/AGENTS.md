# AGENTS.md (VS Code extension)

- Build: `npm install && npm run compile` (TypeScript, strict mode). Debug: open this folder in VS Code and press F5.
- The extension only calls the `codetwin` CLI (`src/cli.ts`) and parses its `--json` output; never re-implement
  analysis here. If the extension needs new data, add a report section or command to the CLI first, with a test.
- One feature per file in `src/features/` exporting a `Feature`; register it with one line in `src/features/index.ts`.
  Do not put feature code in `extension.ts`.
- Shared state (output channel, status bar, last decision, `onDidDecide` event) comes from `Ctx` in `src/context.ts`.
- `Decision` in `src/cli.ts` mirrors `Decision.to_dict()` in `src/codetwin/selection.py` (contract: `docs/output.md`).
- In `package.json`, add your commands, menus and settings as new entries; keep the `codetwin.<feature>.*` prefix.
