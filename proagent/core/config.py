"""ProAgent Configuration - Load and manage proagent.yaml settings."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from proagent.core.ssh_pool import TargetHost

logger = logging.getLogger(__name__)

# Default config search paths
CONFIG_FILENAMES = ["proagent.yaml", "proagent.yml"]


@dataclass
class ModelConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key: str = ""
    base_url: str = ""


@dataclass
class ModelsConfig:
    planner: ModelConfig = field(default_factory=lambda: ModelConfig())
    executor: ModelConfig = field(default_factory=lambda: ModelConfig())
    summarizer: ModelConfig = field(default_factory=lambda: ModelConfig(provider="anthropic", model="claude-3-5-haiku-latest"))


@dataclass
class GatewayConfig:
    enabled: bool = False
    # Platform-specific settings stored as dict
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CronJobConfig:
    name: str = ""
    cron: str = ""
    skill: str = ""
    target: str = ""


@dataclass
class ProAgentConfig:
    """Top-level ProAgent configuration."""
    # Runtime
    domain: str = "server-health-inspector"
    locale: str = "zh-CN"

    # Models
    models: ModelsConfig = field(default_factory=ModelsConfig)

    # Gateways
    gateways: Dict[str, GatewayConfig] = field(default_factory=dict)

    # Targets
    default_target: str = "local"
    targets: List[TargetHost] = field(default_factory=list)

    # Cron
    cron_jobs: List[CronJobConfig] = field(default_factory=list)

    # Policy
    policy_pack: str = "default"

    # Audit
    audit_db: str = "proagent/storage/audit.db"

    # Raw config dict for extensions
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)


def find_config_file(search_dir: Path = None) -> Optional[Path]:
    """Find proagent.yaml in the given directory or current working directory."""
    if search_dir is None:
        search_dir = Path.cwd()

    for filename in CONFIG_FILENAMES:
        path = search_dir / filename
        if path.exists():
            return path

    # Also check ~/.proagent/
    home_dir = Path.home() / ".proagent"
    for filename in CONFIG_FILENAMES:
        path = home_dir / filename
        if path.exists():
            return path

    return None


def load_config(config_path: Path = None) -> ProAgentConfig:
    """Load ProAgent configuration from YAML file.

    Args:
        config_path: Explicit path to config file. If None, searches default locations.

    Returns:
        ProAgentConfig instance with all settings loaded.
    """
    if config_path is None:
        config_path = find_config_file()

    if config_path is None or not config_path.exists():
        logger.info("No proagent.yaml found, using defaults")
        return ProAgentConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config = ProAgentConfig(_raw=raw)

    # Runtime section
    runtime = raw.get("runtime", {})
    config.domain = runtime.get("domain", config.domain)
    config.locale = runtime.get("locale", config.locale)

    # Models section
    models_raw = raw.get("models", {})
    if models_raw:
        config.models = _parse_models(models_raw)

    # Gateways section
    gateways_raw = raw.get("gateways", {})
    for name, gw_config in gateways_raw.items():
        if isinstance(gw_config, dict):
            config.gateways[name] = GatewayConfig(
                enabled=gw_config.get("enabled", True),
                settings=gw_config,
            )
        elif isinstance(gw_config, bool):
            config.gateways[name] = GatewayConfig(enabled=gw_config)

    # Targets section
    targets_raw = raw.get("targets", {})
    config.default_target = targets_raw.get("default", "local")
    hosts = targets_raw.get("hosts", [])
    for host_raw in hosts:
        target = TargetHost(
            id=host_raw.get("id", ""),
            host=host_raw.get("host", ""),
            user=host_raw.get("user", ""),
            port=host_raw.get("port", 22),
            keyfile=host_raw.get("keyfile", ""),
            backend=host_raw.get("backend", "ssh"),
            role=host_raw.get("role", ""),
            owner=host_raw.get("owner", ""),
            note=host_raw.get("note", ""),
        )
        config.targets.append(target)

    # Cron section
    cron_raw = raw.get("cron", {})
    if isinstance(cron_raw, dict):
        cron_enabled = cron_raw.get("enabled", True)
        if cron_enabled:
            jobs = cron_raw.get("jobs", [])
            for job in jobs:
                config.cron_jobs.append(CronJobConfig(
                    name=job.get("name", ""),
                    cron=job.get("cron", ""),
                    skill=job.get("skill", ""),
                    target=job.get("target", config.default_target),
                ))

    # Policy
    policy_raw = raw.get("policy", {})
    config.policy_pack = policy_raw.get("pack", "default")

    # Audit
    audit_raw = raw.get("audit", {})
    config.audit_db = audit_raw.get("db", config.audit_db)

    return config


def _parse_models(raw: Dict[str, Any]) -> ModelsConfig:
    """Parse models section from config."""
    models = ModelsConfig()

    for role in ["planner", "executor", "summarizer"]:
        model_raw = raw.get(role, {})
        if isinstance(model_raw, dict):
            mc = ModelConfig(
                provider=model_raw.get("provider", "openai"),
                model=model_raw.get("model", "gpt-4.1-mini"),
                api_key=_expand_env(model_raw.get("api_key", "")),
                base_url=model_raw.get("base_url", ""),
            )
            setattr(models, role, mc)

    return models


def _expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references in config values."""
    if not value:
        return value
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def save_config(config: ProAgentConfig, config_path: Path) -> None:
    """Save ProAgent configuration to YAML file."""
    data = {
        "runtime": {
            "domain": config.domain,
            "locale": config.locale,
        },
        "models": {
            "planner": {"provider": config.models.planner.provider, "model": config.models.planner.model},
            "executor": {"provider": config.models.executor.provider, "model": config.models.executor.model},
            "summarizer": {"provider": config.models.summarizer.provider, "model": config.models.summarizer.model},
        },
        "gateways": {
            name: {"enabled": gw.enabled, **gw.settings}
            for name, gw in config.gateways.items()
        },
        "targets": {
            "default": config.default_target,
            "hosts": [
                {
                    "id": t.id,
                    "backend": t.backend,
                    **({"host": t.host} if t.backend != "local" else {}),
                    **({"user": t.user} if t.backend != "local" else {}),
                    **({"port": t.port} if t.port != 22 and t.backend != "local" else {}),
                    **({"keyfile": t.keyfile} if t.keyfile else {}),
                    **({"role": t.role} if t.role else {}),
                    **({"owner": t.owner} if t.owner else {}),
                    **({"note": t.note} if t.note else {}),
                }
                for t in config.targets
            ],
        },
        "cron": {
            "enabled": len(config.cron_jobs) > 0,
            "jobs": [
                {"name": j.name, "cron": j.cron, "skill": j.skill, "target": j.target}
                for j in config.cron_jobs
            ],
        },
        "policy": {"pack": config.policy_pack},
        "audit": {"db": config.audit_db},
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Config saved to %s", config_path)
