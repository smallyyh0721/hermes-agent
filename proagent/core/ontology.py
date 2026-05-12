"""Ontology - Load system topology and inject into Agent context.

Parses topology.yaml to give the Agent understanding of:
- What entities exist (nodes, storage, services, k8s)
- How they relate (mounts, stores_on, runs_on, depends_on)
- Where to find metrics for each entity

The topology is rendered as a concise text block for the system prompt.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def load_topology(topology_path: Path) -> Optional[Dict[str, Any]]:
    """Load topology.yaml and return parsed dict."""
    if not topology_path.exists():
        logger.info("No topology.yaml found at %s", topology_path)
        return None

    with open(topology_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data


def render_topology_for_prompt(topology: Dict[str, Any]) -> str:
    """Render topology into a concise text block for the system prompt.

    Produces a human-readable summary that helps the LLM understand
    the system structure without overwhelming the context.
    """
    if not topology:
        return ""

    lines = ["## System Topology (entities & relationships)"]
    lines.append("")

    entities = topology.get("entities", {})

    # Nodes
    nodes = entities.get("nodes", {})
    if nodes:
        lines.append("### Nodes")
        for node_id, info in nodes.items():
            roles = ", ".join(info.get("roles", []))
            host = info.get("host", "?")
            node_type = info.get("type", "")
            hw = info.get("hardware", {})
            hw_str = ""
            if hw:
                parts = [f"{k}={v}" for k, v in hw.items()]
                hw_str = f" [{', '.join(parts)}]"
            lines.append(f"- **{node_id}** ({node_type}) @ {host} — roles: {roles}{hw_str}")

            # Metrics endpoints
            metrics = info.get("metrics", {})
            if metrics:
                for name, url in metrics.items():
                    lines.append(f"  - metrics/{name}: `{url}`")
        lines.append("")

    # Storage
    storage = entities.get("storage", {})
    if storage:
        lines.append("### Storage")
        for store_id, info in storage.items():
            store_type = info.get("type", "")
            store_nodes = info.get("nodes", [])
            notes = info.get("notes", "")
            lines.append(f"- **{store_id}** ({store_type})")
            if store_nodes:
                lines.append(f"  - nodes: {', '.join(store_nodes)}")
            if info.get("mountpoint"):
                lines.append(f"  - mountpoint: {info['mountpoint']}")
            if info.get("clients"):
                lines.append(f"  - clients: {', '.join(info['clients'])}")
            if info.get("metrics"):
                lines.append(f"  - metrics: `{info['metrics']}`")
            if notes:
                lines.append(f"  - note: {notes}")
        lines.append("")

    # Kubernetes
    k8s = entities.get("kubernetes", {})
    if k8s:
        lines.append("### Kubernetes")
        for cluster_id, info in k8s.items():
            lines.append(f"- **{cluster_id}** (k8s)")
            if info.get("api_server"):
                lines.append(f"  - API: {info['api_server']}")
            if info.get("master_nodes"):
                lines.append(f"  - masters: {', '.join(info['master_nodes'])}")
            if info.get("worker_nodes"):
                lines.append(f"  - workers: {', '.join(info['worker_nodes'])}")
            if info.get("namespaces"):
                lines.append(f"  - namespaces: {', '.join(info['namespaces'])}")
        lines.append("")

    # Services
    services = entities.get("services", {})
    if services and not (len(services) == 1 and "placeholder" in services):
        lines.append("### Services")
        for svc_id, info in services.items():
            if svc_id == "placeholder":
                continue
            svc_type = info.get("type", "")
            runs_on = info.get("runs_on", [])
            depends = info.get("depends_on", [])
            lines.append(f"- **{svc_id}** ({svc_type})")
            if runs_on:
                lines.append(f"  - runs on: {', '.join(runs_on)}")
            if depends:
                lines.append(f"  - depends on: {', '.join(depends)}")
        lines.append("")

    # Relationships
    relationships = topology.get("relationships", [])
    if relationships:
        lines.append("### Relationships")
        for rel in relationships:
            fr = rel.get("from", "?")
            to = rel.get("to", "?")
            rel_type = rel.get("type", "?")
            detail = rel.get("detail", "")
            detail_str = f" ({detail})" if detail else ""
            lines.append(f"- {fr} —[{rel_type}]→ {to}{detail_str}")
        lines.append("")

    return "\n".join(lines)


def load_and_render_topology(domain_dir: Path) -> str:
    """Convenience: load topology.yaml from domain knowledge/ and render for prompt."""
    topology_path = domain_dir / "knowledge" / "topology.yaml"
    topology = load_topology(topology_path)
    if topology is None:
        return ""
    return render_topology_for_prompt(topology)
