"use client";

// Evidence-typed dependency graph, drawn with Cytoscape as a layered diagram (dagre, top to bottom: a file above
// depends on files below it). Nodes are cards with their name inside, coloured by the area of the
// repository they belong to (fixed categorical order, at most seven areas plus "other"); tests have a dashed outline.
// Edge colours and dash styles are the evidence types (same as the VS Code impact panel).
import type { Core, ElementDefinition, Ext, LayoutOptions, StylesheetJson } from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Graph, GraphNode } from "@/lib/api";

export const EDGE_STYLES: Record<string, { color: string; style: "solid" | "dashed" | "dotted" }> = {
  static: { color: "#8b90a8", style: "solid" },
  runtime: { color: "#5b8cff", style: "solid" },
  "co-change": { color: "#e8912d", style: "dashed" },
  declared: { color: "#b180d7", style: "solid" },
  suggested: { color: "#b180d7", style: "dashed" },
  unresolved: { color: "#6e6e6e", style: "dotted" },
};

// Categorical slots 1..7 (dataviz reference palette), light and dark steps. Slot 8 is not used: an eighth area
// and beyond fold into "other" (neutral), never a generated hue.
const SLOTS_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"];
const SLOTS_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9"];
const OTHER = "#8b90a8";

/** The area of a path: the first folder below what every path shares (`src/codetwin/lang/x.py` -> `lang` when
 *  every path starts with `src/codetwin/`); files directly in that shared folder are `core`. */
export function areaOf(path: string, prefix: string): string {
  if (prefix && !path.startsWith(prefix)) return path.split("/")[0] || "core";   // e.g. tests/ next to src/pkg/
  const rest = path.slice(prefix.length);
  const i = rest.indexOf("/");
  return i > 0 ? rest.slice(0, i) : "core";             // a file directly in the shared folder
}

/** The longest folder that most paths (60%) sit in, e.g. `src/codetwin/` next to a `tests/` folder: areas are
 *  the folders below it. Paths outside it are areas by their top folder. */
function sharedPrefix(paths: string[]): string {
  const dirs = paths.filter((p) => p && p !== "?").map((p) => p.split("/").slice(0, -1));
  let prefix: string[] = [];
  for (;;) {
    const count = new Map<string, number>();
    for (const d of dirs) {
      if (d.length > prefix.length && prefix.every((s, i) => d[i] === s)) count.set(d[prefix.length], (count.get(d[prefix.length]) ?? 0) + 1);
    }
    const best = [...count].sort((a, b) => b[1] - a[1])[0];
    if (!best || best[1] < dirs.length * 0.6) break;       // no single folder holds most paths
    prefix = [...prefix, best[0]];
  }
  return prefix.length ? prefix.join("/") + "/" : "";
}

/** Area -> colour slot (0..6), biggest areas first; ties by name, so the same repository always gets the same
 *  colours. Areas past the seventh get -1 ("other"). */
export function areaSlots(nodes: GraphNode[]): { prefix: string; slots: Map<string, number> } {
  const prefix = sharedPrefix(nodes.filter((n) => n.kind !== "unknown").map((n) => (n.files ? `${n.path}/x` : n.path)));
  const size = new Map<string, number>();
  for (const n of nodes) {
    if (n.kind === "unknown") continue;
    const a = areaOf(n.files ? `${n.path}/x` : n.path, prefix);
    size.set(a, (size.get(a) ?? 0) + (n.files ?? 1));
  }
  const order = [...size].sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0])).map(([a]) => a);
  return { prefix, slots: new Map(order.map((a, i) => [a, i < SLOTS_LIGHT.length ? i : -1])) };
}

function isDark(): boolean {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function GraphView({ graph, root, onOpen, onSelect, search, selected, colourBy }: {
  graph: Graph; root?: string; onOpen?: (path: string) => void;
  /** the nodes area colours are computed from (default: this graph's). Pass the whole repository so an area keeps
   *  its colour in every view and filter. */
  colourBy?: GraphNode[];
  /** node id to show as selected (e.g. chosen from search results); kept across graph rebuilds */
  selected?: string | null;
  /** called with the node id on click (or null on background click); lets a page show a side panel */
  onSelect?: (id: string | null) => void;
  /** nodes whose label or path contains this text stay bright, others fade */
  search?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | undefined>(undefined);
  // Bumped when a new Cytoscape instance is ready, so the search effect re-applies to it (setup is async).
  const [ready, setReady] = useState(0);
  const areas = useMemo(() => areaSlots(colourBy ?? graph.nodes), [colourBy, graph]);
  useEffect(() => {
    let cy: Core | undefined;
    let cancelled = false;
    Promise.all([import("cytoscape"), import("cytoscape-dagre"), import("cytoscape-fcose")])
      .then(([{ default: cytoscape }, { default: dagre }, { default: fcose }]) => {
      if (cancelled || !ref.current) return;
      registerOnce(cytoscape, [dagre, fcose]);
      const layered = !!root || graph.nodes.some((n) => n.files);
      // Tests reach almost everything; their links are drawn lighter so the structure of the code stays readable.
      // Only in the folder view: in a folder's files the test links are the point.
      const tests = new Set(graph.nodes.some((n) => n.files) ? graph.nodes.filter((n) => n.kind === "test").map((n) => n.id) : []);
      const elements: ElementDefinition[] = [
        ...graph.nodes.map((n) => {
          // a folder is named relative to the shared folder (`commands · 21`, not `src/codetwin/commands · 21`)
          const rel = n.files && areas.prefix && `${n.path}/`.startsWith(areas.prefix) ? n.path.slice(areas.prefix.length) : n.path;
          const name = n.files ? `${rel || n.path.split("/").pop()} · ${n.files}` : fileName(n.label);
          const area = n.kind === "unknown" ? "" : areaOf(n.files ? `${n.path}/x` : n.path, areas.prefix);
          return { data: { ...n, label: name, area, slot: areas.slots.get(area) ?? -1,
            w: Math.max(48, name.length * 7.2 + 24) } };
        }),
        ...graph.edges.map((e, i) => ({ data: { id: `e${i}`, ...e, width: e.weight ? 1 + Math.log2(e.weight) * 0.9 : 1.2,
          fromTest: tests.has(e.source) ? 1 : 0 } })),
      ];
      cy = cytoscape({
        container: ref.current,
        elements,
        // Folders and impact trees are layered (dagre); a folder's files with their neighbours are mostly two layers
        // (tests and code), which dagre draws as one long row, so they get a force layout that respects card sizes.
        layout: (layered
          ? { name: "dagre", rankDir: "TB", nodeSep: 22, rankSep: root ? 44 : 40, edgeSep: 8, ranker: "network-simplex",
              padding: 24, animate: false }
          : { name: "fcose", quality: "proof", animate: false, randomize: true, nodeDimensionsIncludeLabels: true,
              nodeRepulsion: () => 12000, idealEdgeLength: () => 90, edgeElasticity: () => 0.2, gravity: 0.25,
              nodeSeparation: 40, padding: 24 }) as unknown as LayoutOptions,
        style: graphStyle(isDark()),
        minZoom: 0.1,
        maxZoom: 2.5,
        wheelSensitivity: 0.25,
      });
      cyRef.current = cy;
      setReady((n) => n + 1);
      cy.on("mouseover", "node", (e) => {
        const hood = e.target.closedNeighborhood();
        // Search hits (and their links) stay bright while hovering something else.
        const hits = cy!.nodes(".hit");
        cy!.elements().not(hood).not(hits).not(hits.connectedEdges()).addClass("hover-faded");
        hood.addClass("lit");
      });
      cy.on("mouseout", "node", () => cy!.elements().removeClass("hover-faded lit"));
      if (onSelect) {
        cy.on("tap", "node", (e) => onSelect(e.target.id()));
        cy.on("tap", (e) => { if (e.target === cy) onSelect(null); });
      }
      if (onOpen && onSelect) {
        // Cytoscape's dbltap does not check that both taps hit the same node; open only on two taps on one node.
        let last: { id: string; at: number } | null = null;
        cy.on("tap", "node", (e) => {
          const id = e.target.id(), at = e.timeStamp;
          if (last && last.id === id && at - last.at < 400) onOpen(e.target.data("path"));
          last = { id, at };
        });
      } else if (onOpen) {
        cy.on("tap", "node", (e) => onOpen(e.target.data("path")));
      }
    });
    return () => {
      cancelled = true;
      cy?.destroy();
      cyRef.current = undefined;
    };
  }, [graph, root, onOpen, onSelect, areas]);
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const q = (search ?? "").trim().toLowerCase();
    cy.elements().removeClass("search-faded hit");
    if (q) {
      const hit = cy.nodes().filter((n) => `${n.data("label")} ${n.data("path")}`.toLowerCase().includes(q));
      hit.addClass("hit");
      cy.elements().not(hit).not(hit.connectedEdges()).addClass("search-faded");
    }
  }, [search, graph, ready]);
  // Selection from outside (search results), and again after a rebuild.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes(":selected").unselect();
    if (selected) cy.getElementById(selected).select();
  }, [selected, graph, ready]);
  // Colours follow the theme: the toggle changes data-theme, the system can change its scheme.
  useEffect(() => {
    const restyle = () => cyRef.current?.style(graphStyle(isDark()));
    const obs = new MutationObserver(restyle);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", restyle);
    return () => {
      obs.disconnect();
      mq.removeEventListener("change", restyle);
    };
  }, [ready]);
  const legend = [...areas.slots].filter(([a]) => a).sort((x, y) => (x[1] < 0 ? 99 : x[1]) - (y[1] < 0 ? 99 : y[1]));
  const others = legend.filter(([, s]) => s < 0).length;
  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-xl border border-border bg-card-2/40"
        style={{ backgroundImage: "radial-gradient(circle, color-mix(in oklab, var(--muted) 22%, transparent) 1px, transparent 1px)",
                 backgroundSize: "18px 18px" }}>
        <div ref={ref} className="h-[640px] w-full" />
        <button type="button" onClick={() => cyRef.current?.fit(undefined, 24)}
          className="absolute right-3 top-3 rounded-lg border border-border bg-card px-2.5 py-1 text-xs text-muted shadow-sm hover:text-foreground">
          Fit
        </button>
      </div>
      {legend.length > 1 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Areas">
          {legend.filter(([, s]) => s >= 0).map(([a, s]) => (
            <li key={a} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: `var(--area-${s})` }} aria-hidden />
              {a}
            </li>
          ))}
          {others > 0 && (
            <li className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: OTHER }} aria-hidden />
              other ({others})
            </li>
          )}
          <li className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-3.5 rounded-sm border border-dashed border-muted" aria-hidden /> test
          </li>
        </ul>
      )}
      <style>{`:root{${SLOTS_LIGHT.map((c, i) => `--area-${i}:${c};`).join("")}}
        :root[data-theme="dark"]{${SLOTS_DARK.map((c, i) => `--area-${i}:${c};`).join("")}}
        @media (prefers-color-scheme: dark){:root:not([data-theme="light"]){${SLOTS_DARK.map((c, i) => `--area-${i}:${c};`).join("")}}}`}</style>
    </div>
  );
}

let registered = false;
function registerOnce(cytoscape: { use: (ext: Ext) => void }, exts: Ext[]) {
  if (!registered) {
    exts.forEach((e) => cytoscape.use(e));
    registered = true;
  }
}

const fileName = (label: string) => label.split("/").pop() || label;

/** The whole stylesheet; replaced as a unit on a theme change, so rule order (and :selected) is kept. */
function graphStyle(dark: boolean): StylesheetJson {
  const fg = dark ? "#eceef7" : "#14151a";
  const card = dark ? "#12141c" : "#ffffff";
  const slots = dark ? SLOTS_DARK : SLOTS_LIGHT;
  return [
    // Cards: the name inside, an area-coloured outline and a light tint of the same colour. Text stays in ink.
    { selector: "node", style: {
      shape: "round-rectangle", width: "data(w)", height: 28, label: "data(label)", color: fg, "font-size": 12,
      "font-family": "ui-sans-serif, system-ui, sans-serif", "text-valign": "center", "text-halign": "center",
      "background-color": card, "border-width": 1.5, "border-color": OTHER, "min-zoomed-font-size": 5 } },
    ...slots.map((c, i) => ({ selector: `node[slot = ${i}]`, style: { "border-color": c, "background-color": mix(card, c, dark ? 0.26 : 0.16) } })),
    { selector: "node[slot = -1]", style: { "background-color": mix(card, OTHER, 0.14) } },
    { selector: "node[files]", style: { height: 32, "font-weight": 600 } },
    { selector: "node[kind = 'test']", style: { "border-style": "dashed" } },
    { selector: "node[kind = 'target']", style: { "border-width": 3, "font-weight": 700 } },
    { selector: "node[kind = 'unknown']", style: { shape: "diamond", width: 22, height: 22, label: "", "background-color": OTHER, "border-width": 0 } },
    { selector: "node:selected", style: { "border-width": 3, "border-color": "#7c7cff", "underlay-color": "#7c7cff", "underlay-opacity": 0.18, "underlay-padding": 4 } },
    { selector: "node.lit, node.hit", style: { "underlay-color": fg, "underlay-opacity": 0.08, "underlay-padding": 4 } },
    // Edges: thin, right-angled, recessive until a node is hovered.
    { selector: "edge", style: { width: "data(width)", opacity: 0.4, "curve-style": "unbundled-bezier",
      "control-point-distances": [18], "control-point-weights": [0.5], "target-arrow-shape": "triangle", "arrow-scale": 0.6 } },
    ...Object.entries(EDGE_STYLES).map(([type, s]) => ({
      selector: `edge[type = '${type}']`,
      style: { "line-color": s.color, "target-arrow-color": s.color, "line-style": s.style },
    })),
    { selector: "edge[fromTest = 1]", style: { opacity: 0.12 } },
    { selector: "edge.lit", style: { opacity: 0.9 } },
    // Last, so they win over the base opacities. Hover and search fade separately, so one never clears the other.
    { selector: ".hover-faded, .search-faded", style: { opacity: 0.08 } },
  ] as StylesheetJson;
}

/** `base` blended toward `tint` by `t` (0..1), as a hex colour. */
function mix(base: string, tint: string, t: number): string {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [a, b] = [p(base), p(tint)];
  return "#" + a.map((x, i) => Math.round(x + (b[i] - x) * t).toString(16).padStart(2, "0")).join("");
}

export function Legend() {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-muted">
      {Object.entries(EDGE_STYLES).map(([type, s]) => (
        <span key={type} className="inline-flex items-center gap-1">
          <span className="inline-block w-5" style={{ borderTop: `2px ${s.style} ${s.color}` }} />
          {type}
        </span>
      ))}
    </div>
  );
}
