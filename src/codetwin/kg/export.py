"""Export the knowledge graph in standard formats.

* JSON (node-link, the D3 / NetworkX format) for the dashboard and for scripts.
* GraphML (XML standard) for Gephi, yEd, Cytoscape and Neo4j (APOC `apoc.import.graphml`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from .graph import KnowledgeGraph


def to_json(kg: KnowledgeGraph) -> dict[str, Any]:
    data = nx.node_link_data(kg.g, edges="links")
    data["stats"] = kg.stats()
    return data


def write(kg: KnowledgeGraph, path: str | Path, fmt: str = "json") -> Path:
    p = Path(path)
    if fmt == "json":
        p.write_text(json.dumps(to_json(kg), indent=1, default=str))
    elif fmt == "graphml":
        g: nx.MultiDiGraph = nx.MultiDiGraph()
        # GraphML only stores scalar attributes; drop None and stringify the rest consistently
        for n, d in kg.g.nodes(data=True):
            g.add_node(n, **{k: v for k, v in d.items() if v is not None and isinstance(v, (str, int, float, bool))})
        for u, v, d in kg.g.edges(data=True):
            g.add_edge(u, v, **{k: val for k, val in d.items() if isinstance(val, (str, int, float, bool))})
        nx.write_graphml(g, p)
    else:
        raise ValueError(f"unknown format {fmt!r}; use json or graphml")
    return p
