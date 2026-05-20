"""prompt_optimize - Refine a user idea into a high-quality image generation prompt.

This is a pure-text transformation that augments the user's idea with style,
composition, lighting, and quality cues. It does NOT call the image generator.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


# Style presets — each is a recipe of additional prompt segments
STYLE_PRESETS = {
    "auto": "highly detailed, professional, sharp focus, 8k resolution",
    "photo": "photorealistic, cinematic lighting, shallow depth of field, 35mm lens, professional photography",
    "anime": "anime style, vibrant colors, detailed line art, studio quality, expressive",
    "oil-painting": "oil painting, brushwork visible, rich colors, classical composition, museum quality",
    "watercolor": "watercolor painting, soft edges, paper texture, pastel palette, fluid gradients",
    "concept-art": "concept art, dramatic lighting, atmospheric perspective, fantasy, ArtStation trending",
    "3d-render": "octane render, ray tracing, physically based rendering, ultra detailed, studio lighting",
    "minimalist": "minimalist composition, negative space, single subject, clean background, geometric",
    "cyberpunk": "cyberpunk, neon lights, rain-slick streets, holograms, futuristic megacity, blade runner",
    "pixar": "pixar style, 3d animated, charming character design, soft lighting, family-friendly",
}

# Quality boosters — applied to all prompts
QUALITY_BOOSTERS = "best quality, masterpiece, highly detailed"

# Common negative prompts
DEFAULT_NEGATIVE = "low quality, blurry, distorted, watermark, signature, text artifacts, deformed"


def prompt_optimize_handler(
    idea: str,
    style: str = "auto",
    aspect_ratio: str = "1:1",
    extra_hints: str = "",
    **_kwargs,
) -> str:
    """Optimize a user idea into a polished image generation prompt.

    Args:
        idea: User's free-form description of what they want
        style: One of: auto | photo | anime | oil-painting | watercolor |
               concept-art | 3d-render | minimalist | cyberpunk | pixar
        aspect_ratio: Target aspect ratio (e.g. "16:9", "1:1", "9:16")
        extra_hints: Additional user constraints (color palette, mood, etc.)

    Returns:
        Multi-line text containing the optimized positive prompt, negative prompt,
        and recommended generation parameters.
    """
    style_key = (style or "auto").lower().strip()
    if style_key not in STYLE_PRESETS:
        style_key = "auto"

    style_segment = STYLE_PRESETS[style_key]
    user_idea = idea.strip()

    # Build the optimized prompt
    parts = [user_idea, style_segment, QUALITY_BOOSTERS]
    if extra_hints.strip():
        parts.append(extra_hints.strip())
    optimized = ", ".join(p for p in parts if p)

    # Suggested parameters
    output = f"""✨ 优化后的提示词

**Style**: {style_key}
**Aspect Ratio**: {aspect_ratio}

**Positive Prompt**:
{optimized}

**Negative Prompt**:
{DEFAULT_NEGATIVE}

**建议生成参数**:
- aspect_ratio: {aspect_ratio}
- count: 4 (推荐生成 4 张变体)
- 可调风格: {", ".join(STYLE_PRESETS.keys())}

提示：使用 image_generate_batch 工具进行多图生成。
"""
    return output
