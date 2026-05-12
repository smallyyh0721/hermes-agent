"""Target Import - Batch import hosts from hosts.yaml with range expansion.

Supports:
- defaults section (user, port, backend, keyfile)
- range syntax: id: gpu-{01..04}, host: 10.11.5.{1..4}
- roles and tags per host
- merge into existing proagent.yaml targets
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from proagent.core.ssh_pool import TargetHost

logger = logging.getLogger(__name__)

# Pattern for range expansion: {01..04} or {1..10}
_RANGE_PATTERN = re.compile(r'\{(\d+)\.\.(\d+)\}')


def expand_range(template: str) -> List[str]:
    """Expand a string with {N..M} range syntax into a list of strings.

    Examples:
        "gpu-{01..04}" → ["gpu-01", "gpu-02", "gpu-03", "gpu-04"]
        "10.11.5.{1..4}" → ["10.11.5.1", "10.11.5.2", "10.11.5.3", "10.11.5.4"]
        "no-range" → ["no-range"]
    """
    match = _RANGE_PATTERN.search(template)
    if not match:
        return [template]

    start_str, end_str = match.group(1), match.group(2)
    start, end = int(start_str), int(end_str)
    # Preserve zero-padding width
    width = len(start_str) if start_str.startswith('0') and len(start_str) > 1 else 0

    results = []
    for i in range(start, end + 1):
        if width:
            value = str(i).zfill(width)
        else:
            value = str(i)
        expanded = template[:match.start()] + value + template[match.end():]
        results.append(expanded)

    return results


def parse_hosts_yaml(path: Path) -> List[TargetHost]:
    """Parse a hosts.yaml file and return a list of TargetHost objects.

    Args:
        path: Path to hosts.yaml

    Returns:
        List of TargetHost objects with ranges expanded and defaults applied.
    """
    if not path.exists():
        raise FileNotFoundError(f"hosts.yaml not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    defaults = raw.get("defaults", {})
    hosts_raw = raw.get("hosts", [])

    targets: List[TargetHost] = []

    for entry in hosts_raw:
        # Expand ranges in id and host
        ids = expand_range(entry.get("id", ""))
        hosts = expand_range(entry.get("host", ""))

        # If host has fewer expansions than id, repeat the last host
        if len(hosts) == 1 and len(ids) > 1:
            hosts = hosts * len(ids)
        elif len(hosts) != len(ids):
            # Zip them; truncate to shorter
            pass

        for idx, (target_id, host) in enumerate(zip(ids, hosts)):
            target = TargetHost(
                id=target_id,
                host=host,
                user=entry.get("user", defaults.get("user", "")),
                port=entry.get("port", defaults.get("port", 22)),
                keyfile=entry.get("keyfile", defaults.get("keyfile", "")),
                backend=entry.get("backend", defaults.get("backend", "ssh")),
                role=",".join(entry.get("roles", [])) if entry.get("roles") else entry.get("role", ""),
                owner=entry.get("owner", defaults.get("owner", "")),
                note=entry.get("note", ""),
            )
            targets.append(target)

    return targets


def import_hosts(hosts_path: Path, config_path: Path = None) -> Tuple[int, int]:
    """Import hosts from hosts.yaml into proagent.yaml.

    Args:
        hosts_path: Path to hosts.yaml
        config_path: Path to proagent.yaml (auto-detected if None)

    Returns:
        Tuple of (added_count, updated_count)
    """
    from proagent.core.config import load_config, save_config, find_config_file

    new_targets = parse_hosts_yaml(hosts_path)

    if config_path is None:
        config_path = find_config_file()
    if config_path is None:
        config_path = Path.cwd() / "proagent.yaml"

    config = load_config(config_path)

    # Build existing target map
    existing = {t.id: t for t in config.targets}

    added = 0
    updated = 0
    for target in new_targets:
        if target.id in existing:
            # Update existing
            existing[target.id] = target
            updated += 1
        else:
            existing[target.id] = target
            added += 1

    config.targets = list(existing.values())
    save_config(config, config_path)

    return added, updated
