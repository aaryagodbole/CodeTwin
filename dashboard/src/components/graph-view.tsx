"use client";

// Evidence-typed graph, drawn with Cytoscape (same edge styles as the VS Code impact panel).
// The project map groups files into their folders (compound nodes) and lays them out with fCoSE, so a real
// repository reads as modules and their links instead of one hairball; an impact view is a tree from its target.
import type { Core, ElementDefinition, Ext, LayoutOptions, StylesheetJson } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import type { Graph } from "@/lib/api";
import { folderOf } from "@/lib/folders";

export const EDGE_STYLES: Record<string, { color: string; style: "solid" | "dashed" | "dotted" }> = {
  static: { color: "#8b90a8", style: "solid" },
  runtime: { color: "#5b8cff", style: "solid" },
  "co-change": { color: "#e8912d", style: "dashed" },
  declared: { color: "#b180d7", style: "solid" },
  suggested: { color: "#b180d7", style: "dashed" },
  unresolved: { color: "#6e6e6e", style: "dotted" },
};

export function GraphView({ graph, root, onOpen, onSelect, search, selected }: {
  graph: Graph; root?: string; onOpen?: (path: string) => void;
  /** node id to show as selected (e.g. chosen from search results); kept across graph rebuilds */
  selected?: string | null;
  /** called with the node id on click (or null on background click); lets a page show a side panel */
  onSelect?: (id: string | null) => void;
  /** nodes whose label or path contains this text stay bright, others fade */
  search?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | undefined>(undefined);
  const searchable = search !== undefined;   // the dependency graph has a search box; the impact view has none
  // Bumped when a new Cytoscape instance is ready, so the search effect re-applies to it (setup is async).
  const [ready, setReady] = useState(0);
  useEffect(() => {
    let cy: Core | undefined;
    let cancelled = false;
    Promise.all([import("cytoscape"), import("cytoscape-fcose")]).then(([{ default: cytoscape }, { default: fcose }]) => {
      if (cancelled || !ref.current) return;
      registerOnce(cytoscape, fcose);
      // The map groups files by folder; an impact view (root set) is a tree and keeps flat nodes.
      // Files are grouped into their folders, nested like the tree (src/codetwin holds src/codetwin/lang), except in
      // an impact view (a tree from its target) and in the folder view (its nodes already are folders).
      const grouped = !root && !graph.nodes.some((n) => n.kind === "module");
      const folders = grouped ? folderTree(graph.nodes.filter((n) => n.kind !== "unknown").map((n) => n.path)) : new Map();
      const elements: ElementDefinition[] = [
        ...[...folders].map(([id, f]) => ({ data: { id, label: f.label, kind: "folder", parent: f.parent } })),
        ...graph.nodes.map((n) => ({ data: { ...n, label: n.kind === "module" || n.kind === "test" && n.files ? n.label : fileName(n.label),
          parent: folders.size && n.kind !== "unknown" ? `dir:${folderOf(n.path)}` : undefined } })),
        ...graph.edges.map((e, i) => ({ data: { id: `e${i}`, ...e, width: e.weight ? 1 + Math.log2(e.weight) * 1.3 : 1.5 } })),
      ];
      const [fg, ring] = themeColours();
      const degree = new Map<string, number>();
      for (const e of graph.edges) {
        degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
        degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
      }
      const sorted = [...degree.values()].sort((a, b) => a - b);
      // In a big graph only the best-connected nodes keep a permanent label; others show it on hover or search.
      // With no links at all (every link type switched off) no node gets one: Infinity labels nothing.
      // Only where a search can bring hidden labels back (the dependency graph); the impact view labels every node.
      const labelFrom = searchable && graph.nodes.length > 60
        ? (sorted.length ? sorted[Math.floor(sorted.length * 0.8)] : Infinity) : 0;
      elements.forEach((el) => {
        if (el.data.kind === "folder" || el.data.source) return;
        const d = degree.get(String(el.data.id)) ?? 0;
        el.data.deg = d;
        // a folder node is as big as the files it holds; a file as big as its links
        el.data.size = el.data.files ? 14 + Math.sqrt(el.data.files) * 5 : 12 + Math.min(d, 24) * 0.9;
        el.data.showLabel = el.data.files || d >= labelFrom ? 1 : 0;
      });
      cy = cytoscape({
        container: ref.current,
        elements,
        layout: root
          ? { name: "breadthfirst", directed: true, roots: [root], spacingFactor: 1.2 }
          : ({ name: "fcose", quality: "proof", animate: false, randomize: true,
               // fewer, bigger nodes (folder view) need more room for their labels
               nodeRepulsion: () => (grouped ? 9000 : 60000), idealEdgeLength: () => (grouped ? 70 : 170),
               edgeElasticity: () => (grouped ? 0.3 : 0.1), nestingFactor: 0.15, gravity: grouped ? 0.3 : 0.15,
               gravityCompound: 1.2, gravityRangeCompound: 1.4, tile: true, packComponents: true,
               nodeSeparation: 60, padding: 24 } as unknown as LayoutOptions),
        minZoom: 0.15,
        maxZoom: 3,
        wheelSensitivity: 0.25,
        style: graphStyle(fg, ring),
      });
      cyRef.current = cy;
      setReady((n) => n + 1);
      cy.on("mouseover", "node:childless", (e) => {
        const hood = e.target.closedNeighborhood();
        // Search hits (and their links) stay bright while hovering something else.
        const hits = cy!.nodes(".hit");
        cy!.elements().not(hood).not(hits).not(hits.connectedEdges()).addClass("hover-faded");
        hood.addClass("lit");
      });
      cy.on("mouseout", "node:childless", () => cy!.elements().removeClass("hover-faded lit"));
      if (onSelect) {
        cy.on("tap", "node:childless", (e) => onSelect(e.target.id()));
        cy.on("tap", (e) => { if (e.target === cy) onSelect(null); });
      }
      if (onOpen && onSelect) {
        // Cytoscape's dbltap does not check that both taps hit the same node; open only on two taps on one node.
        let last: { id: string; at: number } | null = null;
        cy.on("tap", "node:childless", (e) => {
          const id = e.target.id(), at = e.timeStamp;
          if (last && last.id === id && at - last.at < 400) onOpen(e.target.data("path"));
          last = { id, at };
        });
      } else if (onOpen) {
        cy.on("tap", "node:childless", (e) => onOpen(e.target.data("path")));
      }
    });
    return () => {
      cancelled = true;
      cy?.destroy();
      cyRef.current = undefined;
    };
  }, [graph, root, onOpen, onSelect, searchable]);
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const q = (search ?? "").trim().toLowerCase();
    cy.elements().removeClass("search-faded hit");
    if (q) {
      const hit = cy.nodes(":childless").filter((n) => `${n.data("label")} ${n.data("path")}`.toLowerCase().includes(q));
      hit.addClass("hit");
      cy.elements().not(hit).not(hit.connectedEdges()).not(hit.ancestors()).addClass("search-faded");
    }
  }, [search, graph, ready]);
  // Selection from outside (search results), and again after a rebuild.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes(":selected").unselect();
    if (selected) cy.getElementById(selected).select();
  }, [selected, graph, ready]);
  // Label and ring colours follow the theme: the toggle changes data-theme, the system can change its scheme.
  useEffect(() => {
    const restyle = () => {
      const cy = cyRef.current;
      if (!cy) return;
      const [fg, ring] = themeColours();
      cy.style(graphStyle(fg, ring));
    };
    const obs = new MutationObserver(restyle);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", restyle);
    return () => {
      obs.disconnect();
      mq.removeEventListener("change", restyle);
    };
  }, [ready]);
  return (
    <div className="relative">
      <div ref={ref} className="h-[640px] w-full rounded-xl border border-border bg-card-2/40" />
      <button type="button" onClick={() => cyRef.current?.fit(undefined, 24)}
        className="absolute right-3 top-3 rounded-lg border border-border bg-card px-2.5 py-1 text-xs text-muted shadow-sm hover:text-foreground">
        Fit
      </button>
    </div>
  );
}

let registered = false;
function registerOnce(cytoscape: { use: (ext: Ext) => void }, ext: Ext) {
  if (!registered) {
    cytoscape.use(ext);
    registered = true;
  }
}

const fileName = (label: string) => label.split("/").pop() || label;

/** One compound node per folder that holds a file (id `dir:<folder>`), side by side (not nested: nested boxes
 *  overlap in a force layout). Only for 2 to 12 folders: one box says nothing, many boxes are noise. */
function folderTree(paths: string[]): Map<string, { label: string; parent?: string }> {
  const holding = [...new Set(paths.map(folderOf))];
  if (holding.length < 2 || holding.length > 12) return new Map();
  return new Map(holding.map((f) => [`dir:${f}`, { label: `${f}/` }]));
}

/** Colours the graph takes from the current theme: label text and the ring around nodes. */
function themeColours(): [string, string] {
  const fg = getComputedStyle(document.body).color;
  const ring = getComputedStyle(document.documentElement).getPropertyValue("--card").trim() || "#ffffff";
  return [fg, ring];
}

/** The whole stylesheet; replaced as a unit on a theme change, so rule order (and :selected) is kept. */
function graphStyle(fg: string, ring: string): StylesheetJson {
  return [
    { selector: "node", style: { label: "data(label)", "font-size": 10, color: fg, "text-valign": "bottom", "text-margin-y": 4, width: "data(size)", height: "data(size)", "text-opacity": 0, "min-zoomed-font-size": 6, "background-color": "#6d6af0", "border-width": 2, "border-color": ring, "border-opacity": 0.6 } },
    // Folders: a quiet box with the folder path on top; files sit inside it.
    { selector: "node[kind = 'folder']", style: { shape: "round-rectangle", "background-color": fg, "background-opacity": 0.04, "border-width": 1, "border-color": fg, "border-opacity": 0.18, "border-style": "solid", label: "data(label)", "text-opacity": 0.7, "text-valign": "top", "text-halign": "center", "text-margin-y": -4, "font-size": 9, "font-weight": 600, padding: "14px", "min-zoomed-font-size": 4 } },
    { selector: "node[kind = 'target']", style: { "background-color": "#f5b324", width: 24, height: 24 } },
    { selector: "node[kind = 'test']", style: { "background-color": "#2fbf71", shape: "round-rectangle" } },
    { selector: "node[kind = 'module']", style: { shape: "round-rectangle", "background-color": "#6d6af0", "font-size": 11, "font-weight": 600 } },
    { selector: "node[files]", style: { "text-valign": "bottom", "text-margin-y": 5, "text-background-color": ring, "text-background-opacity": 0.85, "text-background-padding": "2px", "text-background-shape": "round-rectangle" } },
    { selector: "node[kind = 'unknown']", style: { "background-color": "#6e6e6e", shape: "diamond" } },
    { selector: "node[showLabel = 1], node:selected, node.lit, node.hit", style: { "text-opacity": 1 } },
    // A label the user asked for (hover, search, selection) shows at any zoom, not only above the minimum size.
    { selector: "node:selected, node.lit, node.hit", style: { "min-zoomed-font-size": 0 } },
    { selector: "edge", style: { opacity: 0.45 } },
    { selector: "node:selected", style: { "border-width": 3, "border-color": "#7c7cff" } },
    { selector: "edge", style: { width: "data(width)", "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.7 } },
    ...Object.entries(EDGE_STYLES).map(([type, s]) => ({
      selector: `edge[type = '${type}']`,
      style: { "line-color": s.color, "target-arrow-color": s.color, "line-style": s.style },
    })),
    // Last, so they win over the base edge opacity. Hover and search fade separately, so one never clears the other.
    { selector: ".hover-faded, .search-faded", style: { opacity: 0.1 } },
  ] as StylesheetJson;
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
