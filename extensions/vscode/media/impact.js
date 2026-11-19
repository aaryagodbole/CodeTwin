// Webview script: draws the graph sent by the extension. Runs inside the VS Code webview sandbox.
(function () {
  const vscode = acquireVsCodeApi();
  const styleOf = {
    static: { "line-color": "#8a8a8a", "line-style": "solid" },
    runtime: { "line-color": "#3794ff", "line-style": "solid" },
    "co-change": { "line-color": "#e8912d", "line-style": "dashed" },
    declared: { "line-color": "#b180d7", "line-style": "solid" },
    suggested: { "line-color": "#b180d7", "line-style": "dashed" },
    unresolved: { "line-color": "#6e6e6e", "line-style": "dotted" },
  };
  let cy;
  window.addEventListener("message", (event) => {
    // Only the extension host posts to this webview, and VS Code relays it from the webview's own origin
    // (vscode-webview://...). Ignore anything else, e.g. a page that opened this frame (CVE-2021-41038 class).
    if (event.origin !== window.origin) return;
    const view = event.data && event.data.view;
    if (!view) return;
    document.getElementById("title").textContent = view.target.id;
    document.getElementById("summary").textContent = view.summary;
    const unknowns = document.getElementById("unknowns");
    unknowns.replaceChildren(...view.unknowns.map((u) => Object.assign(document.createElement("li"), { textContent: u })));
    const elements = [
      ...view.nodes.map((n) => ({ data: { id: n.id, label: n.label, kind: n.kind, path: n.path } })),
      ...view.edges.map((e, i) => ({ data: { id: "e" + i, source: e.source, target: e.target, type: e.type, detail: e.detail || "" } })),
    ];
    if (cy) cy.destroy();
    cy = cytoscape({
      container: document.getElementById("graph"),
      elements,
      layout: { name: "breadthfirst", directed: true, spacingFactor: 1.2, roots: [view.target.id] },
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 11, color: getComputedStyle(document.body).color, "text-valign": "bottom", "text-margin-y": 4, width: 18, height: 18, "background-color": "#8a8a8a" } },
        { selector: "node[kind = 'target']", style: { "background-color": "#f5c518", width: 26, height: 26 } },
        { selector: "node[kind = 'test']", style: { "background-color": "#3fb950", shape: "round-rectangle" } },
        { selector: "node[kind = 'unknown']", style: { "background-color": "#6e6e6e", shape: "diamond" } },
        { selector: "edge", style: { width: 2, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.8 } },
        ...Object.entries(styleOf).map(([t, s]) => ({ selector: `edge[type = '${t}']`, style: { ...s, "target-arrow-color": s["line-color"] } })),
      ],
    });
    cy.on("tap", "node", (e) => {
      const p = e.target.data("path");
      if (p && e.target.data("kind") !== "unknown") vscode.postMessage({ open: p });
    });
    cy.on("mouseover", "edge", (e) => { document.getElementById("summary").textContent = `${e.target.data("type")}: ${e.target.data("detail")}`; });
    cy.on("mouseout", "edge", () => { document.getElementById("summary").textContent = view.summary; });
  });
})();
