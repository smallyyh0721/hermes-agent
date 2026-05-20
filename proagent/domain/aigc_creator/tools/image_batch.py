"""image_generate_batch - Generate up to 8 image variants for a prompt.

Wraps the existing aigc_generate_handler in a loop, varying seeds/aspect
ratios to produce diverse outputs. Logs each generation to a SQLite history.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from proagent.domain.aigc_creator.tools.aigc_generate import aigc_generate_handler

logger = logging.getLogger(__name__)

# History DB lives next to the audit DB
HISTORY_DB = Path.cwd() / "proagent" / "storage" / "aigc_history.db"

# Hard cap on batch size
MAX_IMAGES = 8


def _ensure_history_db():
    """Create history DB and table on first use."""
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HISTORY_DB))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aigc_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            aspect_ratio TEXT,
            variant_index INTEGER,
            output_path TEXT,
            success INTEGER,
            error TEXT,
            rating TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _record_history(
    prompt: str,
    aspect_ratio: str,
    variant_index: int,
    output_path: str,
    success: bool,
    error: str = "",
) -> int:
    """Insert a row in history; returns inserted row id."""
    _ensure_history_db()
    conn = sqlite3.connect(str(HISTORY_DB))
    cursor = conn.execute(
        "INSERT INTO aigc_history (ts, prompt, aspect_ratio, variant_index, output_path, success, error, rating) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
        (int(time.time()), prompt, aspect_ratio, variant_index, output_path, 1 if success else 0, error),
    )
    rid = cursor.lastrowid
    conn.commit()
    conn.close()
    return rid


def image_generate_batch_handler(
    prompt: str,
    count: int = 4,
    aspect_ratio: str = "1:1",
    **_kwargs,
) -> str:
    """Generate `count` image variants for the given prompt (max 8).

    Args:
        prompt: The optimized image generation prompt
        count: Number of variants to generate (1..8)
        aspect_ratio: Aspect ratio (e.g. "1:1", "16:9", "9:16")

    Returns:
        Multi-line summary listing each generated file path with its history id.
    """
    if count < 1:
        count = 1
    if count > MAX_IMAGES:
        count = MAX_IMAGES

    results: List[Dict[str, Any]] = []
    for i in range(count):
        # Vary seed-like options across variants
        options = f"--aspect-ratio {aspect_ratio}"
        # mmx supports --seed flag; pass per-variant seed for reproducibility
        seed = int(time.time() * 1000) + i
        options += f" --seed {seed}"

        single_result = aigc_generate_handler(
            command="image generate",
            prompt=prompt,
            options=options,
        )

        success = single_result.startswith("✅")
        # Try to extract output path from result
        output_path = ""
        if success:
            for line in single_result.splitlines():
                if line.startswith("文件:") or line.startswith("File:"):
                    output_path = line.split(":", 1)[1].strip()
                    break

        history_id = _record_history(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            variant_index=i + 1,
            output_path=output_path,
            success=success,
            error="" if success else single_result[:200],
        )
        results.append({
            "variant": i + 1,
            "history_id": history_id,
            "success": success,
            "output_path": output_path,
            "raw": single_result,
        })

    # Build summary
    success_count = sum(1 for r in results if r["success"])
    lines = [
        f"🎨 批量生图完成 ({success_count}/{count} 成功)",
        f"提示词: {prompt[:120]}{'...' if len(prompt) > 120 else ''}",
        f"宽高比: {aspect_ratio}",
        "",
        "结果:",
    ]
    for r in results:
        marker = "✅" if r["success"] else "❌"
        if r["success"]:
            lines.append(f"  {marker} #{r['variant']} (id={r['history_id']}) → {r['output_path']}")
        else:
            err_brief = r["raw"].splitlines()[0] if r["raw"] else "unknown error"
            lines.append(f"  {marker} #{r['variant']} (id={r['history_id']}) {err_brief[:120]}")
    lines.append("")
    lines.append("使用 image_feedback(image_id, rating) 记录评分（best/good/bad）")
    return "\n".join(lines)


def image_history_list_handler(limit: int = 20, **_kwargs) -> str:
    """List recent image generations from history.

    Args:
        limit: Max rows to return (default 20)

    Returns:
        Markdown-formatted table of recent generations.
    """
    _ensure_history_db()
    conn = sqlite3.connect(str(HISTORY_DB))
    rows = conn.execute(
        "SELECT id, ts, prompt, aspect_ratio, variant_index, output_path, success, rating "
        "FROM aigc_history ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 200)),),
    ).fetchall()
    conn.close()

    if not rows:
        return "📭 暂无生成历史"

    lines = [
        f"📚 生成历史（最近 {len(rows)} 条）",
        "",
        "| ID | 时间 | 状态 | 比例 | 变体 | 评分 | 提示词摘要 |",
        "|----|------|------|------|------|------|------------|",
    ]
    for r in rows:
        rid, ts, prompt, ratio, variant, output_path, success, rating = r
        ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        status = "✅" if success else "❌"
        rating_str = rating or "-"
        prompt_brief = (prompt or "")[:60].replace("|", "/").replace("\n", " ")
        lines.append(f"| {rid} | {ts_str} | {status} | {ratio or '-'} | {variant or '-'} | {rating_str} | {prompt_brief} |")
    return "\n".join(lines)


def image_feedback_handler(image_id: int, rating: str, **_kwargs) -> str:
    """Record a user rating for a generated image.

    Args:
        image_id: History row id
        rating: One of "best", "good", "bad"

    Returns:
        Confirmation message.
    """
    rating_norm = (rating or "").lower().strip()
    if rating_norm not in ("best", "good", "bad"):
        return f"❌ rating 必须是 best/good/bad，收到: {rating}"
    _ensure_history_db()
    conn = sqlite3.connect(str(HISTORY_DB))
    cursor = conn.execute(
        "UPDATE aigc_history SET rating = ? WHERE id = ?",
        (rating_norm, int(image_id)),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        return f"⚠️  未找到 image_id={image_id}"
    return f"✅ 已记录 image_id={image_id} 评分为 {rating_norm}"
