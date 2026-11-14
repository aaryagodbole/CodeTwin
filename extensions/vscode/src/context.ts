// Shared state handed to every feature: output channel, status bar, workspace root and the last decision.
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { Decision } from "./cli";

export class Ctx {
  readonly output = vscode.window.createOutputChannel("CodeTwin AI");
  readonly status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  private readonly decided = new vscode.EventEmitter<Decision>();
  /** Fires after every `select`; features such as gutters or CodeLens refresh on it. */
  readonly onDidDecide = this.decided.event;
  lastDecision: Decision | undefined;

  constructor(readonly extension: vscode.ExtensionContext) {
    extension.subscriptions.push(this.output, this.status, this.decided);
  }

  root(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }

  /** Has this repository been set up (`codetwin init` wrote .codetwin.toml)? */
  configured(): boolean {
    const r = this.root();
    return !!r && fs.existsSync(path.join(r, ".codetwin.toml"));
  }

  setDecision(d: Decision): void {
    this.lastDecision = d;
    this.decided.fire(d);
  }

  /** Run `fn` with the workspace root; shows errors instead of throwing. */
  async withRoot(fn: (cwd: string) => Promise<void>): Promise<void> {
    const cwd = this.root();
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

  /** Register a command and dispose it with the extension. */
  command(id: string, fn: () => unknown): void {
    this.extension.subscriptions.push(vscode.commands.registerCommand(id, fn));
  }
}
