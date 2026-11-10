// CodeTwin AI for VS Code. Features live in src/features/ (one file each); this file only starts them.
import * as vscode from "vscode";
import { Ctx } from "./context";
import { features } from "./features";

export function activate(context: vscode.ExtensionContext): void {
  const ctx = new Ctx(context);
  for (const f of features) {
    try {
      f.activate(ctx);
    } catch (e) {
      ctx.output.appendLine(`feature ${f.id} failed to start: ${(e as Error).message}`);
    }
  }
}

export function deactivate(): void {}
