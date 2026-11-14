// F1 Select-to-Impact: select code (or hover a function) and see its impact graph beside the editor.
// Edge styles show how each link is known: static (solid), runtime (blue), co-change (orange dashed),
// unresolved (grey dotted). The graph comes from `codetwin graph --json`; nothing is computed here.
import * as path from "path";
import * as vscode from "vscode";
import { runCli } from "../cli";
import { Ctx } from "../context";
import { Feature } from "./types";

export interface GraphTarget {
  file: string; // repository-relative path
  start: number; // 1-based, inclusive
  end: number;
}

export interface GraphView {
  target: { id: string; label: string };
  nodes: { id: string; label: string; kind: string; path: string }[];
  edges: { source: string; target: string; type: string; detail?: string }[];
  unknowns: string[];
  counts: { tests: number; importers: number; unknown: number };
  summary: string;
}

const cache = new Map<string, { at: number; view: GraphView }>();
const CACHE_MS = 30_000;

export async function loadGraph(cwd: string, t: GraphTarget): Promise<GraphView> {
  const key = `${t.file}:${t.start}-${t.end}`;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < CACHE_MS) {
    return hit.view;
  }
  const view = JSON.parse(await runCli(["graph", t.file, "--lines", `${t.start}-${t.end}`, "--json"], cwd)) as GraphView;
  cache.set(key, { at: Date.now(), view });
  return view;
}

function relPath(cwd: string, doc: vscode.TextDocument): string {
  return path.relative(cwd, doc.uri.fsPath).split(path.sep).join("/");
}

/** The block of a `def`/`class` starting at `line` (0-based), found by indentation. */
/** Languages CodeTwin has an adapter for (VS Code language ids). */
export const LANGUAGES = [
  "python", "javascript", "typescript", "javascriptreact", "typescriptreact", "go", "java", "kotlin", "rust",
  "csharp", "ruby", "php", "c", "cpp",
];

const BLOCK_KINDS = new Set([
  vscode.SymbolKind.Function, vscode.SymbolKind.Method, vscode.SymbolKind.Constructor, vscode.SymbolKind.Class,
  vscode.SymbolKind.Interface, vscode.SymbolKind.Struct, vscode.SymbolKind.Enum,
]);

/** Function or class declared on `line`, from the language's own symbol provider (any language). */
export async function symbolBlockAt(doc: vscode.TextDocument, line: number): Promise<vscode.Range | undefined> {
  if (doc.languageId === "python") {
    return blockAt(doc, line);
  }
  let symbols: vscode.DocumentSymbol[] | undefined;
  try {
    symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>("vscode.executeDocumentSymbolProvider", doc.uri);
  } catch {
    return undefined;
  }
  let best: vscode.DocumentSymbol | undefined;
  const visit = (list: vscode.DocumentSymbol[] | undefined) => {
    for (const s of list ?? []) {
      if (s.range.start.line <= line && line <= s.range.end.line) {
        if (BLOCK_KINDS.has(s.kind) && s.selectionRange.start.line === line) {
          best = s;
        }
        visit(s.children);
      }
    }
  };
  visit(symbols);
  return best?.range;
}

export function blockAt(doc: vscode.TextDocument, line: number): vscode.Range | undefined {
  const text = doc.lineAt(line).text;
  const m = /^(\s*)(async\s+)?(def|class)\s/.exec(text);
  if (!m) {
    return undefined;
  }
  const indent = m[1].length;
  let end = line;
  for (let i = line + 1; i < doc.lineCount; i++) {
    const t = doc.lineAt(i).text;
    if (t.trim() === "") {
      continue;
    }
    if (t.length - t.trimStart().length <= indent) {
      break;
    }
    end = i;
  }
  return new vscode.Range(line, 0, end, doc.lineAt(end).text.length);
}

async function targetFor(cwd: string, editor: vscode.TextEditor): Promise<GraphTarget> {
  const sel = editor.selection;
  let range: vscode.Range = sel;
  if (sel.isEmpty) {
    range = (await symbolBlockAt(editor.document, sel.active.line)) ??
      new vscode.Range(sel.active.line, 0, sel.active.line, 0);
  }
  return { file: relPath(cwd, editor.document), start: range.start.line + 1, end: range.end.line + 1 };
}

class ImpactPanel {
  private panel: vscode.WebviewPanel | undefined;
  constructor(private readonly ctx: Ctx) {}

  get open(): boolean {
    return this.panel !== undefined;
  }

  async show(cwd: string, t: GraphTarget, reveal = true): Promise<void> {
    const view = await loadGraph(cwd, t);
    if (!this.panel) {
      const media = vscode.Uri.joinPath(this.ctx.extension.extensionUri, "media");
      this.panel = vscode.window.createWebviewPanel(
        "codetwin.impact",
        "CodeTwin: impact",
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
        { enableScripts: true, localResourceRoots: [media], retainContextWhenHidden: true }
      );
      this.panel.onDidDispose(() => (this.panel = undefined));
      this.panel.webview.onDidReceiveMessage(async (msg: { open?: string }) => {
        if (msg.open) {
          const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(cwd, msg.open)));
          await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);
        }
      });
      this.panel.webview.html = this.html(this.panel.webview, media);
    } else if (reveal) {
      this.panel.reveal(vscode.ViewColumn.Beside, true);
    }
    this.panel.title = `Impact: ${view.target.label}`;
    await this.panel.webview.postMessage({ view });
  }

  private html(webview: vscode.Webview, media: vscode.Uri): string {
    const nonce = Math.random().toString(36).slice(2);
    const lib = webview.asWebviewUri(vscode.Uri.joinPath(media, "cytoscape.min.js"));
    const app = webview.asWebviewUri(vscode.Uri.joinPath(media, "impact.js"));
    const css = webview.asWebviewUri(vscode.Uri.joinPath(media, "impact.css"));
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
<link rel="stylesheet" href="${css}"></head><body>
<header><strong id="title">CodeTwin impact</strong> <span id="summary"></span></header>
<div id="legend"><span class="static">static</span><span class="runtime">runtime</span><span class="co-change">co-change</span><span class="unresolved">unresolved</span></div>
<div id="graph"></div><ul id="unknowns"></ul>
<script nonce="${nonce}" src="${lib}"></script><script nonce="${nonce}" src="${app}"></script>
</body></html>`;
  }
}

export const impactPanel: Feature = {
  id: "impactPanel",
  activate(ctx) {
    const panel = new ImpactPanel(ctx);
    const showFor = (editor: vscode.TextEditor | undefined, t?: GraphTarget) =>
      ctx.withRoot(async (cwd) => {
        const target = t ?? (editor ? await targetFor(cwd, editor) : undefined);
        if (target) {
          await panel.show(cwd, target);
        }
      });

    ctx.command("codetwin.showImpactGraph", (t?: GraphTarget) => showFor(vscode.window.activeTextEditor, t));

    // Hover a function/class or a selection: one-line summary with a link that opens the graph beside.
    ctx.extension.subscriptions.push(
      vscode.languages.registerHoverProvider(LANGUAGES.map((language) => ({ language, scheme: "file" })), {
        async provideHover(doc, pos) {
          const cwd = ctx.root();
          const editor = vscode.window.activeTextEditor;
          if (!cwd || !vscode.workspace.getConfiguration("codetwin").get<boolean>("graph.hover", true)) {
            return undefined;
          }
          let range: vscode.Range | undefined;
          if (editor && editor.document === doc && !editor.selection.isEmpty && editor.selection.contains(pos)) {
            range = editor.selection;
          } else {
            range = await symbolBlockAt(doc, pos.line);
          }
          if (!range) {
            return undefined;
          }
          const t: GraphTarget = { file: relPath(cwd, doc), start: range.start.line + 1, end: range.end.line + 1 };
          try {
            const v = await loadGraph(cwd, t);
            const args = encodeURIComponent(JSON.stringify([t]));
            const md = new vscode.MarkdownString(
              `**CodeTwin** · ${v.summary} · [Show impact graph](command:codetwin.showImpactGraph?${args})`
            );
            md.isTrusted = { enabledCommands: ["codetwin.showImpactGraph"] };
            return new vscode.Hover(md, range);
          } catch {
            return undefined;
          }
        },
      })
    );

    // While the panel is open, follow the selection.
    let timer: NodeJS.Timeout | undefined;
    ctx.extension.subscriptions.push(
      vscode.window.onDidChangeTextEditorSelection((e) => {
        if (!panel.open || !LANGUAGES.includes(e.textEditor.document.languageId)) {
          return;
        }
        if (!vscode.workspace.getConfiguration("codetwin").get<boolean>("graph.followSelection", true)) {
          return;
        }
        clearTimeout(timer);
        timer = setTimeout(() => {
          const cwd = ctx.root();
          if (cwd) {
            targetFor(cwd, e.textEditor).then((tg) => panel.show(cwd, tg, false)).catch(() => undefined);
          }
        }, 600);
      }),
      vscode.workspace.onDidSaveTextDocument(() => cache.clear())
    );
  },
};
