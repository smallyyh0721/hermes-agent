"""SRE write_report tools - The ONLY two write actions allowed for SRE agent.

These tools write diagnosis reports and inspection reports to the local
filesystem under proagent/storage/reports/. All other write actions are
denied by Policy Guard.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Output directory for reports
REPORTS_DIR = Path.cwd() / "proagent" / "storage" / "reports"


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in text)
    safe = "-".join(filter(None, safe.split("-")))  # collapse dashes
    return safe[:max_len].strip("-") or "report"


def write_diagnosis_report_handler(
    target: str,
    summary: str,
    evidence: str = "",
    severity: str = "medium",
    suggested_steps: str = "",
    **_kwargs,
) -> str:
    """Write a fault diagnosis report to disk.

    Args:
        target: Target host/system being diagnosed (e.g. "web-01" or "ceph-cluster")
        summary: One-paragraph summary of the issue and root cause hypothesis
        evidence: Raw evidence (logs, command outputs, metrics) supporting the diagnosis
        severity: One of "low", "medium", "high", "critical"
        suggested_steps: Suggested remediation steps (text, NOT to be executed)

    Returns:
        Path to the written report file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now()
    timestamp_str = ts.strftime("%Y-%m-%d_%H%M%S")
    target_slug = _slugify(target or "unknown")
    filename = f"diagnosis-{timestamp_str}-{target_slug}.md"
    out_path = REPORTS_DIR / filename

    content = f"""# 故障诊断报告 — {target}

**生成时间**: {ts.strftime("%Y-%m-%d %H:%M:%S")}
**严重等级**: {severity.upper()}
**目标系统**: {target}

---

## 摘要

{summary}

## 证据

```
{evidence if evidence else '(no evidence collected)'}
```

## 建议处置步骤（仅建议，未执行）

{suggested_steps if suggested_steps else '(no suggested steps provided)'}

---

> ⚠️ 本报告由 ProAgent SRE Agent 自动生成。
> 处置步骤为建议，**未自动执行**。请人工审核后再执行。
"""

    out_path.write_text(content, encoding="utf-8")
    logger.info("SRE diagnosis report written: %s", out_path)
    return f"✅ 故障诊断报告已生成\n路径: {out_path.resolve()}\n大小: {len(content)} 字节"


def write_inspection_report_handler(
    target: str,
    kind: str,
    summary: str,
    metrics: str = "",
    issues: str = "",
    **_kwargs,
) -> str:
    """Write an inspection report to disk.

    Args:
        target: Target host (e.g. "web-01")
        kind: Type of inspection: "quick", "full", or "scheduled"
        summary: One-paragraph health summary
        metrics: Key metrics in plain text (CPU/mem/disk/net snapshots)
        issues: Identified issues, one per line (or "none" if healthy)

    Returns:
        Path to the written report file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now()
    timestamp_str = ts.strftime("%Y-%m-%d_%H%M%S")
    target_slug = _slugify(target or "unknown")
    filename = f"inspection-{kind}-{timestamp_str}-{target_slug}.md"
    out_path = REPORTS_DIR / filename

    status = "🟢 健康" if issues.strip().lower() in ("", "none", "无") else "🟡 注意"

    content = f"""# 巡检报告 — {target}

**生成时间**: {ts.strftime("%Y-%m-%d %H:%M:%S")}
**巡检类型**: {kind}
**目标系统**: {target}
**整体状态**: {status}

---

## 摘要

{summary}

## 关键指标

```
{metrics if metrics else '(no metrics collected)'}
```

## 发现的问题

{issues if issues else '无 (None)'}

---

> 由 ProAgent SRE Agent 自动生成。本巡检为只读操作，未执行任何系统变更。
"""

    out_path.write_text(content, encoding="utf-8")
    logger.info("SRE inspection report written: %s", out_path)
    return f"✅ 巡检报告已生成\n路径: {out_path.resolve()}\n状态: {status}"
