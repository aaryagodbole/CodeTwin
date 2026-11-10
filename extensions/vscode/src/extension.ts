// CodeTwin AI for VS Code (skeleton).
// Planned features (paper, Table IV): select-to-impact panel, impact CodeLens, blind-spot highlighting,
// test-gap gutter and recommended tests in the Test Explorer. This skeleton wires the commands to the CLI.
import * as path from "path";
import * as vscode from "vscode";
import { runCli, selectTests } from "./cli";

let output: vscode.OutputChannel;
let status: vscode.StatusBarItem;

function root(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

async function withRoot(fn: (cwd: string) => Promise<void>): Promise<void> {
  const cwd = root();
  if (!cwd) {
    vscode.window.showWarningMessage("CodeTwin: open a folder first.");
    return;
  }
  try {
    await fn(cwd);
  } catch (e) {
    vscode.window.showErrorMessage(`CodeTwin: ${(e as Error).message}`);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  output = vscode.window.createOutputChannel("CodeTwin AI");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = "codetwin.selectTests";
  status.text = "$(beaker) CodeTwin";
  status.show();

  context.subscriptions.push(
    output,
    status,
    vscode.commands.registerCommand("codetwin.selectTests", () =>
      withRoot(async (cwd) => {
        const d = await selectTests(cwd);
        const risk = (d.residual_risk * 100).toFixed(1);
        status.text = `$(beaker) ${d.decision === "proceed" ? "proceed" : "run more"} · risk ${risk}%`;
        output.clear();
        output.appendLine(`Decision: ${d.decision.toUpperCase()}  (estimated residual risk ${risk}%, ${d.mode})`);
        d.reasons.forEach((r) => output.appendLine(`  - ${r}`));
        output.appendLine(`Selected ${d.selected.length} test files:`);
        d.selected.forEach((t) => output.appendLine(`  ${t}`));
        output.show(true);
      })
    ),
    vscode.commands.registerCommand("codetwin.impact", () =>
      withRoot(async (cwd) => {
        const file = vscode.window.activeTextEditor?.document.uri.fsPath;
        if (!file) {
          return;
        }
        const rel = path.relative(cwd, file).split(path.sep).join("/");
        output.clear();
        output.appendLine(`Impact of ${rel}:`);
        output.append(await runCli(["impact", rel], cwd));
        output.show(true);
      })
    ),
    vscode.commands.registerCommand("codetwin.record", () =>
      withRoot(async (cwd) => {
        await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: "CodeTwin: running the suite with coverage..." },
          async () => output.appendLine(await runCli(["record"], cwd))
        );
        output.show(true);
      })
    ),
    vscode.commands.registerCommand("codetwin.explain", () =>
      withRoot(async (cwd) => {
        output.clear();
        output.append(await runCli(["explain"], cwd));
        output.show(true);
      })
    )
  );
}

export function deactivate(): void {}
