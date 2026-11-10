// Thin wrapper around the `codetwin` command-line tool: the extension never re-implements analysis.
import { execFile } from "child_process";
import * as vscode from "vscode";

// Output contract of `codetwin select --json` (docs/output.md). New report sections appear under `extras`.
export interface Decision {
  schema: number;
  decision: "proceed" | "abstain";
  residual_risk: number;
  threshold: number | null;
  mode: string;
  selected: string[];
  reasons: string[];
  extras: Record<string, { summary?: string; [key: string]: unknown }>;
}

export function runCli(args: string[], cwd: string): Promise<string> {
  const cli = vscode.workspace.getConfiguration("codetwin").get<string>("cliPath", "codetwin");
  return new Promise((resolve, reject) => {
    execFile(cli, args[0] === "--version" ? args : ["-C", cwd, ...args], { cwd, maxBuffer: 16 * 1024 * 1024 }, (err, stdout, stderr) => {
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
