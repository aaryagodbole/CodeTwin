"use client";

// Evidence-typed graph, drawn with Cytoscape (same styles as the VS Code impact panel).
import type { Core, ElementDefinition } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import type { Graph } from "@/lib/api";

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
  // Bumped when a new Cytoscape instance is ready, so the search effect re-applies to it (setup is async).
  const [ready, setReady] = useState(0);
  useEffect(() => {
    let cy: Core | undefined;
    let cancelled = false;
    import("cytoscape").then(({ default: cytoscape }) => {
      if (cancelled || !ref.current) return;
      const elements: ElementDefinition[] = [
        ...graph.nodes.map((n) => ({ data: { ...n } })),
        ...graph.edges.map((e, i) => ({ data: { id: `e${i}`, ...e } })),
      ];
      const fg = getComputedStyle(document.body).color;
      const ring = getComputedStyle(document.documentElement).getPropertyValue("--card").trim() || "#ffffff";
      const degree = new Map<string, number>();
      for (const e of graph.edges) {
        degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
        degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
      }
      const sorted = [...degree.values()].sort((a, b) => a - b);
      // In a big graph only the best-connected nodes keep a permanent label; others show it on hover or search.
      // With no links at all (every link type switched off) no node gets one: Infinity labels nothing.
      const labelFrom = graph.nodes.length > 25 ? (sorted.length ? sorted[Math.floor(sorted.length * 0.8)] : Infinity) : 0;
      elements.forEach((el) => {
        const d = degree.get(String(el.data.id)) ?? 0;
        el.data.deg = d;
        el.data.size = 12 + Math.min(d, 24) * 0.9;
        el.data.showLabel = d >= labelFrom ? 1 : 0;
      });
      cy = cytoscape({
        container: ref.current,
        elements,
        layout: root
          ? { name: "breadthfirst", directed: true, roots: [root], spacingFactor: 1.2 }
          : { name: "cose", animate: false, nodeRepulsion: () => 60000, idealEdgeLength: () => 110, nodeOverlap: 24, gravity: 0.4, numIter: 1500 },
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": 10, color: fg, "text-valign": "bottom", "text-margin-y": 4, width: "data(size)", height: "data(size)", "text-opacity": 0, "min-zoomed-font-size": 6, "background-color": "#8b90a8", "border-width": 2, "border-color": ring, "border-opacity": 0.6 } },
          { selector: "node[kind = 'target']", style: { "background-color": "#f5b324", width: 24, height: 24 } },
          { selector: "node[kind = 'test']", style: { "background-color": "#2fbf71", shape: "round-rectangle" } },
          { selector: "node[kind = 'unknown']", style: { "background-color": "#6e6e6e", shape: "diamond" } },
          { selector: "node[showLabel = 1], node:selected, node.lit, node.hit", style: { "text-opacity": 1 } },
          { selector: "edge", style: { opacity: 0.55 } },
          { selector: "node:selected", style: { "border-width": 3, "border-color": "#7c7cff" } },
          { selector: "edge", style: { width: 1.5, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.7 } },
          ...Object.entries(EDGE_STYLES).map(([type, s]) => ({
            selector: `edge[type = '${type}']`,
            style: { "line-color": s.color, "target-arrow-color": s.color, "line-style": s.style },
          })),
          // Last, so they win over the base edge opacity. Hover and search fade separately, so one never clears the other.
          { selector: ".hover-faded, .search-faded", style: { opacity: 0.1 } },
        ],
      });
      cyRef.current = cy;
      setReady((n) => n + 1);
      cy.on("mouseover", "node", (e) => {
        const hood = e.target.closedNeighborhood();
        cy!.elements().not(hood).addClass("hover-faded");
        hood.addClass("lit");
      });
      cy.on("mouseout", "node", () => cy!.elements().removeClass("hover-faded lit"));
      if (onSelect) {
        cy.on("tap", "node", (e) => onSelect(e.target.id()));
        cy.on("tap", (e) => { if (e.target === cy) onSelect(null); });
      }
      if (onOpen) cy.on(onSelect ? "dbltap" : "tap", "node", (e) => onOpen(e.target.data("path")));
    });
    return () => {
      cancelled = true;
      cy?.destroy();
      cyRef.current = undefined;
    };
  }, [graph, root, onOpen, onSelect]);
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
  // Label and ring colours follow the theme: the toggle changes data-theme, the system can change its scheme.
  useEffect(() => {
    const restyle = () => {
      const cy = cyRef.current;
      if (!cy) return;
      const fg = getComputedStyle(document.body).color;
      const ring = getComputedStyle(document.documentElement).getPropertyValue("--card").trim() || "#ffffff";
      cy.style().selector("node").style({ color: fg, "border-color": ring }).update();
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
  return <div ref={ref} className="h-[560px] w-full rounded-xl border border-border bg-card-2/40" />;
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
