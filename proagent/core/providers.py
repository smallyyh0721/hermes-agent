"""Provider registry - Defines supported LLM providers for ProAgent.

Phase 1 supports:
- openai: OpenAI API (chat completions with function calling)
- anthropic: Anthropic Messages API (native tool use)
- minimax-cn: MiniMax China (Anthropic-compatible endpoint)

Additional providers can be added here as the ProAgent matures.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProviderProfile:
    """Configuration for a single LLM provider."""
    id: str                          # Canonical identifier
    display_name: str                # Human-readable name
    api_mode: str                    # "openai" | "anthropic"
    env_vars: List[str]              # Env vars to check for API key
    base_url: str = ""               # Default base URL (empty = use SDK default)
    default_model: str = ""          # Suggested default model
    signup_url: str = ""             # Where to get an API key
    notes: str = ""                  # Extra configuration notes


# Registry of supported providers
PROVIDERS: List[ProviderProfile] = [
    ProviderProfile(
        id="openai",
        display_name="OpenAI",
        api_mode="openai",
        env_vars=["OPENAI_API_KEY"],
        base_url="",  # Use SDK default https://api.openai.com/v1
        default_model="gpt-4.1-mini",
        signup_url="https://platform.openai.com",
    ),
    ProviderProfile(
        id="anthropic",
        display_name="Anthropic",
        api_mode="anthropic",
        env_vars=["ANTHROPIC_API_KEY"],
        base_url="",  # Use SDK default
        default_model="claude-3-5-haiku-latest",
        signup_url="https://console.anthropic.com",
    ),
    ProviderProfile(
        id="minimax-cn",
        display_name="MiniMax China (mainland China endpoint)",
        api_mode="anthropic",
        env_vars=["MINIMAX_CN_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic",
        default_model="MiniMax-M2.7",
        signup_url="https://platform.minimaxi.com",
        notes="Uses Anthropic-compatible API. Suitable for users in mainland China.",
    ),
]

PROVIDER_MAP = {p.id: p for p in PROVIDERS}

# Accepted aliases that normalize to canonical provider IDs
PROVIDER_ALIASES = {
    "minimax_cn": "minimax-cn",
    "minimax-china": "minimax-cn",
    "minimax_china": "minimax-cn",
    "minimax": "minimax-cn",           # Default 'minimax' input to CN (common in this project)
    "claude": "anthropic",
    "gpt": "openai",
}


def resolve_provider(name: str) -> Optional[ProviderProfile]:
    """Resolve a provider name (including aliases) to a ProviderProfile."""
    if not name:
        return None
    normalized = name.strip().lower()
    canonical = PROVIDER_ALIASES.get(normalized, normalized)
    return PROVIDER_MAP.get(canonical)


def list_providers() -> List[ProviderProfile]:
    """Return all registered provider profiles."""
    return list(PROVIDERS)
