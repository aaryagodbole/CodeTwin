// First-run check: the extension needs the `codetwin` CLI (offer to install it) and a repository that has been
// set up (offer `codetwin init` + `codetwin record`, which detect the languages and test runners themselves).
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
    runCli(["--version"], cwd).then(async () => {
      if (ctx.configured() || ctx.extension.workspaceState.get<boolean>("codetwin.setupDeclined")) {
        return;
      }
      const choice = await vscode.window.showInformationMessage(
        "CodeTwin: set up this repository? It detects the languages and test runners, then records which tests " +
          "cover which code (this runs the tests once).",
        "Set up",
        "Not now",
        "Never for this folder"
      );
      if (choice === "Never for this folder") {
        await ctx.extension.workspaceState.update("codetwin.setupDeclined", true);
      } else if (choice === "Set up") {
        await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: "CodeTwin: setting up", cancellable: false },
          async (progress) => {
            try {
              progress.report({ message: "detecting languages" });
              ctx.output.appendLine(await runCli(["init"], cwd));
              progress.report({ message: "recording test coverage" });
              ctx.output.appendLine(await runCli(["record"], cwd));
              vscode.window.showInformationMessage("CodeTwin is ready: edit code, then run 'CodeTwin: Select tests'.");
            } catch (e) {
              ctx.output.appendLine(String((e as Error).message));
              vscode.window.showErrorMessage(`CodeTwin setup: ${(e as Error).message.split("\n")[0]}`);
            }
          }
        );
      }
    }).catch(async () => {
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
