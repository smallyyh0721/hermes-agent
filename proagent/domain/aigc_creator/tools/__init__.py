"""AIGC Creator Tools - Self-registering tool set.

Phase 4: Adds prompt optimization, multi-image batch generation, history & feedback.
"""

from proagent.core.agent import ToolDef
from proagent.domain.aigc_creator.tools.aigc_generate import aigc_generate_handler
from proagent.domain.aigc_creator.tools.prompt_optimize import prompt_optimize_handler
from proagent.domain.aigc_creator.tools.image_batch import (
    image_generate_batch_handler,
    image_history_list_handler,
    image_feedback_handler,
)


def get_tools(runtime) -> list:
    """Return all tools for the AIGC domain."""
    return [
        ToolDef(
            name="prompt_optimize",
            description=(
                "Optimize a user idea into a polished image generation prompt. "
                "Augments the user's description with style, composition, lighting, and quality cues. "
                "Returns positive prompt + negative prompt + recommended generation parameters. "
                "Call this BEFORE image_generate_batch to improve quality."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "idea": {
                        "type": "string",
                        "description": "The user's free-form description of what they want to generate",
                    },
                    "style": {
                        "type": "string",
                        "description": (
                            "Style preset: auto | photo | anime | oil-painting | watercolor | "
                            "concept-art | 3d-render | minimalist | cyberpunk | pixar"
                        ),
                        "default": "auto",
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "description": "Aspect ratio: '1:1', '16:9', '9:16', '4:3', '3:4'",
                        "default": "1:1",
                    },
                    "extra_hints": {
                        "type": "string",
                        "description": "Additional constraints (color palette, mood, etc.)",
                        "default": "",
                    },
                },
                "required": ["idea"],
            },
            handler=prompt_optimize_handler,
            category="suggest",
        ),
        ToolDef(
            name="image_generate_batch",
            description=(
                "Generate multiple image variants for a prompt (max 8 per call). "
                "Each variant uses a different random seed for diversity. "
                "Each result is logged to history with an id you can use with image_feedback."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The optimized image prompt (run prompt_optimize first)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of variants to generate (1-8, default 4)",
                        "default": 4,
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "description": "Aspect ratio: '1:1', '16:9', '9:16', '4:3', '3:4'",
                        "default": "1:1",
                    },
                },
                "required": ["prompt"],
            },
            handler=image_generate_batch_handler,
            category="write_action",
        ),
        ToolDef(
            name="image_history_list",
            description="List recent image generations with their history ids, prompts, and ratings.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=image_history_list_handler,
            category="read_only",
        ),
        ToolDef(
            name="image_feedback",
            description="Record a user rating (best/good/bad) for a generated image by history id.",
            parameters={
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "The history row id (returned by image_generate_batch)",
                    },
                    "rating": {
                        "type": "string",
                        "description": "Rating: best | good | bad",
                    },
                },
                "required": ["image_id", "rating"],
            },
            handler=image_feedback_handler,
            category="write_action",
        ),
        # Keep the original direct CLI passthrough for advanced users
        ToolDef(
            name="aigc_generate",
            description=(
                "Direct passthrough to MiniMax CLI for advanced use. "
                "For standard image generation, prefer prompt_optimize + image_generate_batch."
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
                        "description": "Content description or text",
                    },
                    "options": {
                        "type": "string",
                        "description": "Extra CLI flags",
                        "default": "",
                    },
                },
                "required": ["command", "prompt"],
            },
            handler=aigc_generate_handler,
            category="write_action",
        ),
    ]
