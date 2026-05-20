"""Domain Pack base - Self-describing domain pack protocol.

Each domain pack is a self-contained directory that declares its own
tools, skills, knowledge, policy, and system prompt. The Runtime loads
packs dynamically without hardcoded if/elif chains.

To create a new domain pack:
1. Create proagent/domain/<pack_id>/
2. Add pack.yaml, system_prompt.md, policy.yaml
3. Add tools/__init__.py with get_tools(runtime) → List[ToolDef]
4. Add knowledge/ and skills/ as needed
"""

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class DomainPack:
    """Loaded domain pack — everything the Runtime needs to operate in a domain."""

    id: str
    dir_name: str
    display_name: str
    description: str
    pack_dir: Path
    system_prompt: str
    policy_path: Path
    knowledge_dir: Path
    skills_dir: Path
    requires_ssh: bool = True
    max_iterations: int = 15  # Max tool-calling rounds per user turn
    max_test_steps: int = 50  # Max steps for test execution workflows
    _tools_loader: Optional[Callable] = field(default=None, repr=False)

    def get_tools(self, runtime) -> list:
        """Return the tool list for this domain. Delegates to tools/__init__.py."""
        if self._tools_loader:
            return self._tools_loader(runtime)
        return []

    def get_skills(self) -> List[str]:
        """Return skill file contents from skills/ directory."""
        skills = []
        if self.skills_dir.exists():
            for f in sorted(self.skills_dir.glob("*.md")):
                skills.append(f.read_text(encoding="utf-8"))
        return skills

    def get_knowledge_index(self) -> str:
        """Return knowledge/index.md content if it exists."""
        index = self.knowledge_dir / "index.md"
        if index.exists():
            return index.read_text(encoding="utf-8")
        return ""


def discover_packs(domain_base: Path = None) -> List[Dict[str, Any]]:
    """Discover all available domain packs by scanning the domain/ directory.

    Returns list of dicts with id, dir_name, display_name, description.
    """
    if domain_base is None:
        domain_base = Path(__file__).resolve().parent

    packs = []
    for d in sorted(domain_base.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name == "__pycache__":
            continue
        pack_file = d / "pack.yaml"
        if not pack_file.exists():
            continue
        try:
            with open(pack_file, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
            packs.append({
                "id": meta.get("id", d.name.replace("_", "-")),
                "dir_name": d.name,
                "display_name": meta.get("display_name", d.name),
                "description": meta.get("description", ""),
                "requires_ssh": meta.get("capabilities", {}).get("read_only", True),
            })
        except Exception as e:
            logger.warning("Failed to read pack.yaml in %s: %s", d, e)

    return packs


def load_pack(domain_id: str, domain_base: Path = None) -> Optional[DomainPack]:
    """Load a domain pack by ID. Returns None if not found.

    This is the single entry point for loading a domain. It:
    1. Finds the pack directory
    2. Reads pack.yaml metadata
    3. Loads system_prompt.md
    4. Dynamically imports tools/__init__.py to get get_tools()
    5. Returns a fully-loaded DomainPack instance
    """
    if domain_base is None:
        domain_base = Path(__file__).resolve().parent

    # Find the pack directory (try both hyphenated and underscored names)
    pack_dir = None
    candidates = [
        domain_base / domain_id.replace("-", "_"),
        domain_base / domain_id,
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "pack.yaml").exists():
            pack_dir = candidate
            break

    # Also search by pack.yaml id field
    if pack_dir is None:
        for d in domain_base.iterdir():
            if not d.is_dir() or d.name.startswith("_"):
                continue
            pf = d / "pack.yaml"
            if pf.exists():
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        meta = yaml.safe_load(f) or {}
                    if meta.get("id") == domain_id:
                        pack_dir = d
                        break
                except Exception:
                    continue

    if pack_dir is None:
        logger.error("Domain pack '%s' not found", domain_id)
        return None

    # Load metadata
    with open(pack_dir / "pack.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    # Load system prompt
    prompt_path = pack_dir / "system_prompt.md"
    system_prompt = ""
    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8")

    # Load tools dynamically
    tools_loader = _load_tools_module(pack_dir)

    # Determine if SSH is needed
    capabilities = meta.get("capabilities", {})
    requires_ssh = capabilities.get("read_only", False) or "server_shell" in meta.get("tools", [])

    pack = DomainPack(
        id=meta.get("id", domain_id),
        dir_name=pack_dir.name,
        display_name=meta.get("display_name", pack_dir.name),
        description=meta.get("description", ""),
        pack_dir=pack_dir,
        system_prompt=system_prompt,
        policy_path=pack_dir / "policy.yaml",
        knowledge_dir=pack_dir / "knowledge",
        skills_dir=pack_dir / "skills",
        requires_ssh=requires_ssh,
        max_iterations=meta.get("max_iterations", 15),
        max_test_steps=meta.get("max_test_steps", 50),
        _tools_loader=tools_loader,
    )

    logger.info("Loaded domain pack: %s (%s)", pack.id, pack.display_name)
    return pack


def _load_tools_module(pack_dir: Path) -> Optional[Callable]:
    """Dynamically import tools/__init__.py and return its get_tools function."""
    tools_init = pack_dir / "tools" / "__init__.py"
    if not tools_init.exists():
        return None

    # Build a unique module name to avoid collisions
    module_name = f"proagent.domain.{pack_dir.name}.tools"

    # Add parent to sys.path if needed
    project_root = pack_dir.parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        spec = importlib.util.spec_from_file_location(module_name, str(tools_init))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        get_tools_fn = getattr(module, "get_tools", None)
        if callable(get_tools_fn):
            return get_tools_fn
        else:
            logger.warning("tools/__init__.py in %s has no get_tools() function", pack_dir.name)
            return None
    except Exception as e:
        logger.error("Failed to load tools module from %s: %s", pack_dir, e)
        return None
