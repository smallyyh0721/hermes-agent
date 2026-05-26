"""Phase 5 agent router for Discord/Web/CLI entry points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


AGENT_DOMAINS = {
    "sre": "server-health-inspector",
    "test": "test-agent",
    "develop": "develop-agent",
    "aigc": "aigc-creator",
    "news": "interest-news-agent",
}


@dataclass(frozen=True)
class RoutedMessage:
    agent_id: str
    domain_id: str
    prompt: str
    session_id: str
    control_response: str = ""


class AgentRouter:
    """Routes slash commands to stable Agent identities and domain packs."""

    def __init__(self, session_store=None, work_store=None, usage_store=None):
        self.session_store = session_store
        self.work_store = work_store
        self.usage_store = usage_store
        self._channel_defaults: Dict[str, str] = {}

    def route_message(self, content: str, channel_id: str, user_id: str, source: str = "discord") -> RoutedMessage:
        text = (content or "").strip()
        agent_id = self._channel_defaults.get(channel_id, "sre")
        prompt = text

        if text.startswith("/agent"):
            return self._handle_agent_control(text, channel_id, user_id, source)

        first, _, rest = text.partition(" ")
        command = first.lstrip("/").lower()
        if first.startswith("/") and command in AGENT_DOMAINS:
            agent_id = command
            prompt = rest.strip()

        domain_id = AGENT_DOMAINS[agent_id]
        session_id = f"{source}:{channel_id}:{agent_id}:{user_id}"
        return RoutedMessage(agent_id=agent_id, domain_id=domain_id, prompt=prompt, session_id=session_id)

    def _handle_agent_control(self, text: str, channel_id: str, user_id: str, source: str) -> RoutedMessage:
        parts = text.split()
        default = self._channel_defaults.get(channel_id, "sre")
        session_id = f"{source}:{channel_id}:control:{user_id}"

        if len(parts) >= 3 and parts[1].lower() == "switch":
            requested = parts[2].lower()
            if requested not in AGENT_DOMAINS:
                valid = ", ".join(sorted(AGENT_DOMAINS))
                msg = f"Unknown agent '{requested}'. Valid agents: {valid}"
            else:
                self._channel_defaults[channel_id] = requested
                default = requested
                msg = f"Channel default agent switched to {requested}."
            return RoutedMessage(default, AGENT_DOMAINS[default], "", session_id, msg)

        if len(parts) >= 2 and parts[1].lower() == "status":
            msg = f"ProAgent router ok. channel_default={default}; agents={', '.join(AGENT_DOMAINS)}"
            return RoutedMessage(default, AGENT_DOMAINS[default], "", session_id, msg)

        if len(parts) >= 2 and parts[1].lower() == "usage":
            totals = self.usage_store.daily_totals() if self.usage_store else {}
            msg = (
                "Usage today: "
                f"input={totals.get('input_tokens', 0)}, "
                f"output={totals.get('output_tokens', 0)}, "
                f"cost={totals.get('estimated_cost', 0):.6f}"
            )
            return RoutedMessage(default, AGENT_DOMAINS[default], "", session_id, msg)

        msg = "Agent commands: /agent switch <sre|test|develop|aigc|news>, /agent status, /agent usage"
        return RoutedMessage(default, AGENT_DOMAINS[default], "", session_id, msg)
