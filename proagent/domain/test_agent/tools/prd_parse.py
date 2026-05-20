"""prd_parse - Extract testable requirements from a product manual / PRD.

Reads a markdown document and extracts:
- Numbered/bulleted feature requirements
- "MUST" / "SHALL" / "WHEN ... THEN" acceptance criteria (EARS-style)
- User stories ("As a ..., I want ..., so that ...")

Returns a structured list the test agent can use to generate cases.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


REQUIREMENT_HEADING_RE = re.compile(
    r"^#+\s*(requirement|feature|user story|功能|需求|用户故事)\s*[: ]*(.*)$",
    re.IGNORECASE,
)
EARS_RE = re.compile(
    r"\b(WHEN|IF|WHILE|WHERE|THE\s+system\s+SHALL)\b",
    re.IGNORECASE,
)
USER_STORY_RE = re.compile(
    r"(?:as\s+(?:a|an)|作为)\s+(.+?)[,，]\s*(?:i\s+want|我想|我希望)\s+(.+?)(?:[,，]\s*(?:so\s+that|以便)\s+(.+))?\.?",
    re.IGNORECASE | re.DOTALL,
)


def prd_parse_handler(path: str, max_items: int = 50, **_kwargs) -> str:
    """Parse a PRD/markdown document into testable requirements.

    Args:
        path: Path to markdown file
        max_items: Cap on number of requirements to extract

    Returns:
        Markdown-formatted list of extracted requirements.
    """
    p = Path(path).resolve()
    if not p.exists():
        return f"❌ PRD file not found: {p}"
    if not p.is_file():
        return f"❌ Path is not a file: {p}"

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"❌ Failed to read PRD: {e}"

    headings: List[Dict[str, Any]] = []
    ears_lines: List[str] = []
    user_stories: List[Dict[str, str]] = []
    bullet_features: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        # Headings indicating requirement sections
        m = REQUIREMENT_HEADING_RE.match(line)
        if m:
            headings.append({"type": m.group(1), "title": m.group(2).strip() or "(no title)"})
            continue

        # EARS-style acceptance criteria
        if EARS_RE.search(line) and len(line.strip()) > 10:
            ears_lines.append(line.strip())
            continue

        # Bulleted features (- F1: Foo / 1. Foo)
        b = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.{6,200})$", line)
        if b:
            bullet_features.append(b.group(1).strip())
            continue

    # User stories: search across full content (multiline)
    for m in USER_STORY_RE.finditer(content):
        persona = m.group(1).strip()
        want = m.group(2).strip()
        why = (m.group(3) or "").strip()
        user_stories.append({"persona": persona, "want": want, "why": why})

    # Build output
    lines = [
        f"# PRD 需求解析报告",
        f"**文件**: {p}",
        f"**字节数**: {len(content)}",
        "",
        "## 统计",
        f"- 需求章节数: {len(headings)}",
        f"- EARS 验收条件: {len(ears_lines)}",
        f"- 用户故事: {len(user_stories)}",
        f"- Bullet 功能项: {len(bullet_features)}",
        "",
    ]

    if headings:
        lines.append("## 需求章节")
        for h in headings[:max_items]:
            lines.append(f"- **{h['type']}**: {h['title']}")
        lines.append("")

    if user_stories:
        lines.append("## 用户故事")
        for s in user_stories[:max_items]:
            why_part = f"，以便 {s['why']}" if s["why"] else ""
            lines.append(f"- 作为 **{s['persona']}**，我想 {s['want']}{why_part}")
        lines.append("")

    if ears_lines:
        lines.append("## 验收条件（EARS）")
        for ac in ears_lines[:max_items]:
            lines.append(f"- {ac}")
        lines.append("")

    if bullet_features:
        lines.append("## 功能列表")
        for f in bullet_features[:max_items]:
            lines.append(f"- {f}")
        lines.append("")

    lines.append("---")
    lines.append("提示: 用 test_generate 工具基于上述需求生成测试用例。")

    return "\n".join(lines)
