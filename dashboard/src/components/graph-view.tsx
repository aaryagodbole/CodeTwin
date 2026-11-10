"use client";

// Evidence-typed graph, drawn with Cytoscape (same styles as the VS Code impact panel).
import type { Core, ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";
import type { Graph } from "@/lib/api";

export const EDGE_STYLES: Record<string, { color: string; style: "solid" | "dashed" | "dotted" }> = {
  static: { color: "#8a8a8a", style: "solid" },
  runtime: { color: "#3794ff", style: "solid" },
  "co-change": { color: "#e8912d", style: "dashed" },
  declared: { color: "#b180d7", style: "solid" },
  suggested: { color: "#b180d7", style: "dashed" },
  unresolved: { color: "#6e6e6e", style: "dotted" },
};

export function GraphView({ graph, root, onOpen }: { graph: Graph; root?: string; onOpen?: (path: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
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
          { selector: "node", style: { label: "data(label)", "font-size": 10, color: fg, "text-valign": "bottom", "text-margin-y": 4, width: 16, height: 16, "background-color": "#8a8a8a" } },
          { selector: "node[kind = 'target']", style: { "background-color": "#f5c518", width: 24, height: 24 } },
          { selector: "node[kind = 'test']", style: { "background-color": "#3fb950", shape: "round-rectangle" } },
          { selector: "node[kind = 'unknown']", style: { "background-color": "#6e6e6e", shape: "diamond" } },
          { selector: "edge", style: { width: 1.5, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.7 } },
          ...Object.entries(EDGE_STYLES).map(([type, s]) => ({
            selector: `edge[type = '${type}']`,
            style: { "line-color": s.color, "target-arrow-color": s.color, "line-style": s.style },
          })),
        ],
      });
      if (onOpen) cy.on("tap", "node", (e) => onOpen(e.target.data("path")));
    });
    return () => {
      cancelled = true;
      cy?.destroy();
    };
  }, [graph, root, onOpen]);
  return <div ref={ref} className="h-[560px] w-full rounded-lg border border-border" />;
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
