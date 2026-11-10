// Thin wrapper around the `codetwin` command-line tool: the extension never re-implements analysis.
import { execFile } from "child_process";
import * as vscode from "vscode";

export interface Decision {
  decision: "proceed" | "abstain";
  residual_risk: number;
  threshold: number | null;
  mode: string;
  selected: string[];
  reasons: string[];
}

export function runCli(args: string[], cwd: string): Promise<string> {
  const cli = vscode.workspace.getConfiguration("codetwin").get<string>("cliPath", "codetwin");
  return new Promise((resolve, reject) => {
    execFile(cli, ["-C", cwd, ...args], { cwd, maxBuffer: 16 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(stderr || err.message));
      } else {
        resolve(stdout);
      }
    });
  });
}

export async function selectTests(cwd: string): Promise<Decision> {
  const alpha = vscode.workspace.getConfiguration("codetwin").get<number>("alpha", 0.1);
  return JSON.parse(await runCli(["select", "--json", "--alpha", String(alpha)], cwd)) as Decision;
}
