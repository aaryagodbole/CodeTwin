// Basic commands: select tests, impact of the current file, record evidence, explain the last decision.
import * as path from "path";
import * as vscode from "vscode";
import { runCli, selectTests } from "../cli";
import { Feature } from "./types";

export const commands: Feature = {
  id: "commands",
  activate(ctx) {
    const out = ctx.output;
    ctx.command("codetwin.selectTests", () =>
      ctx.withRoot(async (cwd) => {
        const d = await selectTests(cwd);
        ctx.setDecision(d);
        const risk = (d.residual_risk * 100).toFixed(1);
        out.clear();
        out.appendLine(`Decision: ${d.decision.toUpperCase()}  (estimated residual risk ${risk}%, ${d.mode})`);
        d.reasons.forEach((r) => out.appendLine(`  - ${r}`));
        out.appendLine(`Selected ${d.selected.length} test files:`);
        d.selected.forEach((t) => out.appendLine(`  ${t}`));
        for (const [name, section] of Object.entries(d.extras ?? {})) {
          if (section.summary) {
            out.appendLine(`${name}: ${section.summary}`);
          }
        }
        out.show(true);
      })
    );
    ctx.command("codetwin.impact", () =>
      ctx.withRoot(async (cwd) => {
        const file = vscode.window.activeTextEditor?.document.uri.fsPath;
        if (!file) {
          return;
        }
        const rel = path.relative(cwd, file).split(path.sep).join("/");
        out.clear();
        out.appendLine(`Impact of ${rel}:`);
        out.append(await runCli(["impact", rel], cwd));
        out.show(true);
      })
    );
    ctx.command("codetwin.record", () =>
      ctx.withRoot(async (cwd) => {
        await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: "CodeTwin: running the suite with coverage..." },
          async () => out.appendLine(await runCli(["record"], cwd))
        );
        out.show(true);
      })
    );
    ctx.command("codetwin.explain", () =>
      ctx.withRoot(async (cwd) => {
        out.clear();
        out.append(await runCli(["explain"], cwd));
        out.show(true);
      })
    );
  },
};
