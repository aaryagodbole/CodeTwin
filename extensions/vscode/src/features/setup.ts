// First-run check: the extension needs the `codetwin` CLI. If it is missing, offer to install it.
import * as vscode from "vscode";
import { runCli } from "../cli";
import { Feature } from "./types";

export const setup: Feature = {
  id: "setup",
  activate(ctx) {
    const cwd = ctx.root();
    if (!cwd) {
      return;
    }
    runCli(["--version"], cwd).catch(async () => {
      const cfg = vscode.workspace.getConfiguration("codetwin");
      const choice = await vscode.window.showWarningMessage(
        "CodeTwin: the `codetwin` command-line tool was not found.",
        "Install with pip",
        "Set path"
      );
      if (choice === "Install with pip") {
        const term = vscode.window.createTerminal("CodeTwin setup");
        term.show();
        term.sendText(cfg.get<string>("installCommand", "pip install codetwin"));
      } else if (choice === "Set path") {
        await vscode.commands.executeCommand("workbench.action.openSettings", "codetwin.cliPath");
      }
    });
  },
};
