"use client";

// Evidence-typed graph, drawn with Cytoscape (same styles as the VS Code impact panel).
import type { Core, ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";
import type { Graph } from "@/lib/api";

export const EDGE_STYLES: Record<string, { color: string; style: "solid" | "dashed" | "dotted" }> = {
  static: { color: "#8b90a8", style: "solid" },
  runtime: { color: "#5b8cff", style: "solid" },
  "co-change": { color: "#e8912d", style: "dashed" },
  declared: { color: "#b180d7", style: "solid" },
  suggested: { color: "#b180d7", style: "dashed" },
  unresolved: { color: "#6e6e6e", style: "dotted" },
};

export function GraphView({ graph, root, onOpen, onSelect, search }: {
  graph: Graph; root?: string; onOpen?: (path: string) => void;
  /** called with the node id on click (or null on background click); lets a page show a side panel */
  onSelect?: (id: string | null) => void;
  /** nodes whose label or path contains this text stay bright, others fade */
  search?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | undefined>(undefined);
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
      cy = cytoscape({
        container: ref.current,
        elements,
        layout: root
          ? { name: "breadthfirst", directed: true, roots: [root], spacingFactor: 1.2 }
          : { name: "cose", animate: false, nodeRepulsion: () => 9000 },
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": 10, color: fg, "text-valign": "bottom", "text-margin-y": 4, width: 16, height: 16, "background-color": "#8b90a8", "border-width": 2, "border-color": "#ffffff", "border-opacity": 0.6 } },
          { selector: "node[kind = 'target']", style: { "background-color": "#f5b324", width: 24, height: 24 } },
          { selector: "node[kind = 'test']", style: { "background-color": "#2fbf71", shape: "round-rectangle" } },
          { selector: "node[kind = 'unknown']", style: { "background-color": "#6e6e6e", shape: "diamond" } },
          { selector: ".faded", style: { opacity: 0.12 } },
          { selector: "node:selected", style: { "border-width": 3, "border-color": "#7c7cff" } },
          { selector: "edge", style: { width: 1.5, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.7 } },
          ...Object.entries(EDGE_STYLES).map(([type, s]) => ({
            selector: `edge[type = '${type}']`,
            style: { "line-color": s.color, "target-arrow-color": s.color, "line-style": s.style },
          })),
        ],
      });
      cyRef.current = cy;
      cy.on("mouseover", "node", (e) => {
        const hood = e.target.closedNeighborhood();
        cy!.elements().not(hood).addClass("faded");
        hood.addClass("lit");
      });
      cy.on("mouseout", "node", () => cy!.elements().removeClass("faded lit"));
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
    cy.elements().removeClass("faded");
    if (q) {
      const hit = cy.nodes().filter((n) => `${n.data("label")} ${n.data("path")}`.toLowerCase().includes(q));
      cy.elements().not(hit).not(hit.connectedEdges()).addClass("faded");
    }
  }, [search, graph]);
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
