"""aigc_generate - Execute MiniMax CLI commands for content generation.

Wraps the `mmx` CLI tool for image/speech/music generation.
All operations are local (no SSH), output files saved to ./output/aigc/.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Output directory for generated content
OUTPUT_DIR = Path.cwd() / "output" / "aigc"


def aigc_generate_handler(command: str, prompt: str, options: str = "", **_kwargs) -> str:
    """Execute a MiniMax CLI command for content generation.

    Args:
        command: MiniMax CLI command (e.g. "image generate", "speech synthesize")
        prompt: The content description or text to process
        options: Additional CLI flags (e.g. "--aspect-ratio 16:9", "--voice male-qn-qingse")

    Returns:
        Result message with file path or error.
    """
    # Resolve API key
    api_key = os.environ.get("MINIMAX_CN_API_KEY", "")
    if not api_key:
        return "❌ MINIMAX_CN_API_KEY not set. Cannot generate content."

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the mmx command
    import shutil
    mmx_path = shutil.which("mmx") or shutil.which("minimax-cli")
    if not mmx_path:
        # Try common locations
        for candidate in [
            Path(sys.executable).parent / "Scripts" / "minimax-cli.exe",
            Path(sys.executable).parent / "minimax-cli",
            Path(sys.executable).parent / "Scripts" / "mmx.exe",
            Path(sys.executable).parent / "mmx",
        ]:
            if candidate.exists():
                mmx_path = str(candidate)
                break

    if not mmx_path:
        return "❌ mmx/minimax-cli 命令未找到。请确认已安装: pip install minimax-cli"

    cmd_parts = [mmx_path] + command.split()
    cmd_parts.extend(["--prompt", prompt])
    cmd_parts.extend(["--api-key", api_key])
    cmd_parts.extend(["--region", "cn"])
    cmd_parts.extend(["--out-dir", str(OUTPUT_DIR)])
    cmd_parts.extend(["--non-interactive"])
    cmd_parts.extend(["--quiet"])

    # Add extra options
    if options:
        cmd_parts.extend(options.split())

    # Log (without API key)
    safe_cmd = " ".join(cmd_parts).replace(api_key, "sk-***")
    logger.info("AIGC command: %s", safe_cmd)

    try:
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path.cwd()),
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            # mmx outputs the file path on success
            if output:
                return f"✅ 生成成功！\n文件: {output}\n命令: {safe_cmd}"
            return f"✅ 生成完成。输出目录: {OUTPUT_DIR}"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return f"❌ 生成失败: {error}"

    except subprocess.TimeoutExpired:
        return "❌ 生成超时（120s）。请简化 prompt 或稍后重试。"
    except FileNotFoundError:
        return "❌ mmx 命令未找到。请确认 MiniMax CLI 已安装: pip install minimax-cli"
    except Exception as e:
        return f"❌ 执行错误: {e}"
