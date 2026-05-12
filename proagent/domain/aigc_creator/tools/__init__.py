"""AIGC Creator Tools - Self-registering tool set."""

from proagent.core.agent import ToolDef
from proagent.domain.aigc_creator.tools.aigc_generate import aigc_generate_handler


def get_tools(runtime) -> list:
    """Return all tools for the AIGC domain."""
    return [ToolDef(
        name="aigc_generate",
        description=(
            "Generate AI content (images, speech, music) using MiniMax CLI. "
            "Use command='image generate' for images, 'speech synthesize' for voice. "
            "The prompt describes what to generate. Options are extra CLI flags like '--aspect-ratio 16:9'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "MiniMax CLI command: 'image generate', 'speech synthesize', 'music generate'",
                },
                "prompt": {
                    "type": "string",
                    "description": "Content description (for images) or text to speak (for speech)",
                },
                "options": {
                    "type": "string",
                    "description": "Extra CLI flags, e.g. '--aspect-ratio 16:9' or '--voice male-qn-qingse'",
                    "default": "",
                },
            },
            "required": ["command", "prompt"],
        },
        handler=aigc_generate_handler,
    )]
