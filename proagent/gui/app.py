"""ProAgent Unified GUI — Streamlit-based control center.

Run with:
    streamlit run proagent/gui/app.py

Provides a unified interface to switch between SRE / AIGC / Test agents,
chat with each, view reports, and inspect generation history.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env so API keys are available in this process
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import streamlit as st

from proagent.core.config import load_config, ProAgentConfig
from proagent.core.runtime import ProAgentRuntime
from proagent.core.agent import ProAgent
from proagent.domain.base import discover_packs


# ---- helpers ----------------------------------------------------------------

REPORTS_DIR = PROJECT_ROOT / "proagent" / "storage" / "reports"
AIGC_HISTORY_DB = PROJECT_ROOT / "proagent" / "storage" / "aigc_history.db"
AIGC_OUTPUT_DIR = Path.cwd() / "output" / "aigc"


# Friendly names for the three agents
AGENT_DISPLAY = {
    "server-health-inspector": ("🔧 SRE Agent", "自动诊断 + 定期巡检"),
    "aigc-creator": ("🎨 AIGC Agent", "提示词优化 + 多图生成"),
    "test-agent": ("🧪 Test Agent", "代码扫描 + 测试生成"),
}


@st.cache_resource(show_spinner=False)
def _get_runtime(domain_id: str) -> ProAgentRuntime:
    """Create or return cached runtime for a domain.

    Uses Streamlit's resource cache so each domain runtime is built only once
    per session.
    """
    config = load_config()
    config.domain = domain_id
    runtime = ProAgentRuntime(config=config)
    if runtime.should_init_ssh():
        try:
            runtime.connect_targets()
        except Exception:
            pass
    return runtime


def _build_agent(domain_id: str) -> ProAgent:
    """Build a ProAgent for the given domain."""
    runtime = _get_runtime(domain_id)
    pack = getattr(runtime, "_domain_pack", None)
    max_iter = getattr(pack, "max_iterations", 30) if pack else 30
    config = runtime.config
    mc = config.models.executor
    tools = runtime.get_tools()
    return ProAgent(
        provider=mc.provider,
        model=mc.model,
        system_prompt=runtime.build_hermes_system_prompt(),
        tools=tools,
        base_url=mc.base_url,
        verbose=False,
        max_iterations=max_iter,
        policy_guard=runtime.policy,
    )


def _list_reports() -> List[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def _list_aigc_history(limit: int = 50) -> List[Dict[str, Any]]:
    if not AIGC_HISTORY_DB.exists():
        return []
    conn = sqlite3.connect(str(AIGC_HISTORY_DB))
    rows = conn.execute(
        "SELECT id, ts, prompt, aspect_ratio, output_path, success, rating "
        "FROM aigc_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "ts": r[1],
            "prompt": r[2],
            "aspect_ratio": r[3],
            "output_path": r[4],
            "success": bool(r[5]),
            "rating": r[6] or "-",
        }
        for r in rows
    ]


# ---- UI ---------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="ProAgent 控制中心",
        page_icon="🤖",
        layout="wide",
    )

    st.title("🤖 ProAgent 控制中心")
    st.caption("统一入口：SRE / AIGC / Test 三 Agent 协同")

    # Discover packs once
    available_packs = discover_packs()
    pack_ids = [p["id"] for p in available_packs]

    # ---- sidebar ------------------------------------------------------------
    with st.sidebar:
        st.markdown("### 选择 Agent")
        # Restrict to the three production agents we ship in Phase 4
        ordered = [
            pid for pid in ["server-health-inspector", "aigc-creator", "test-agent"]
            if pid in pack_ids
        ]
        if not ordered:
            st.error("没有发现可用的 Agent Pack")
            return

        selected = st.radio(
            "Agent",
            options=ordered,
            format_func=lambda pid: AGENT_DISPLAY.get(pid, (pid, ""))[0],
            key="selected_agent",
        )

        for pid in ordered:
            label, desc = AGENT_DISPLAY.get(pid, (pid, ""))
            if pid == selected:
                st.caption(f"**{desc}**")

        st.divider()

        page = st.radio(
            "面板",
            options=["💬 对话", "📋 报告库", "🖼️ 图片画廊", "⚙️ 状态"],
            key="page",
        )

        st.divider()
        st.caption("提示：图片画廊只对 AIGC Agent 有意义；")
        st.caption("报告库展示 SRE 写入的诊断/巡检报告。")

    # ---- main panels --------------------------------------------------------
    if page == "💬 对话":
        _render_chat(selected)
    elif page == "📋 报告库":
        _render_reports()
    elif page == "🖼️ 图片画廊":
        _render_gallery()
    elif page == "⚙️ 状态":
        _render_status(selected)


def _render_chat(domain_id: str):
    label, desc = AGENT_DISPLAY.get(domain_id, (domain_id, ""))
    st.subheader(f"{label} — {desc}")

    # Per-agent message history in session state
    history_key = f"chat_history_{domain_id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    # Reset / new conversation button
    cols = st.columns([6, 1])
    with cols[1]:
        if st.button("🔄 新对话", key=f"reset_{domain_id}"):
            st.session_state[history_key] = []
            # Drop cached runtime/agent for this domain to truly reset
            if f"agent_{domain_id}" in st.session_state:
                del st.session_state[f"agent_{domain_id}"]
            st.rerun()

    # Render history
    for msg in st.session_state[history_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    user_input = st.chat_input(f"对 {label} 说点什么…")
    if user_input:
        # Show user message immediately
        st.session_state[history_key].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build / reuse agent
        agent_key = f"agent_{domain_id}"
        if agent_key not in st.session_state:
            try:
                st.session_state[agent_key] = _build_agent(domain_id)
            except Exception as e:
                err = f"❌ Agent 初始化失败：{e}"
                st.session_state[history_key].append({"role": "assistant", "content": err})
                with st.chat_message("assistant"):
                    st.error(err)
                return
        agent: ProAgent = st.session_state[agent_key]

        # Inference
        with st.chat_message("assistant"):
            with st.spinner("Agent 正在思考…"):
                try:
                    response = agent.chat(user_input)
                except Exception as e:
                    response = f"❌ 执行错误：{e}"
            st.markdown(response or "*(空回复)*")
            st.session_state[history_key].append(
                {"role": "assistant", "content": response or "(empty response)"}
            )


def _render_reports():
    st.subheader("📋 SRE 报告库")
    st.caption(f"目录：`{REPORTS_DIR}`")

    reports = _list_reports()
    if not reports:
        st.info("暂无报告。让 SRE Agent 完成一次诊断或巡检后会自动出现。")
        return

    # Summary table
    rows = []
    for p in reports:
        kind = "诊断" if p.name.startswith("diagnosis-") else (
            "巡检" if p.name.startswith("inspection-") else "其他"
        )
        rows.append({
            "名称": p.name,
            "类型": kind,
            "大小 (B)": p.stat().st_size,
            "修改时间": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Detail viewer
    selected_name = st.selectbox(
        "选择报告查看详情",
        options=[p.name for p in reports],
    )
    if selected_name:
        target = next(p for p in reports if p.name == selected_name)
        st.markdown(f"### `{selected_name}`")
        st.markdown(target.read_text(encoding="utf-8"))


def _render_gallery():
    st.subheader("🖼️ AIGC 图片画廊")
    history = _list_aigc_history(limit=100)
    if not history:
        st.info("暂无生成记录。让 AIGC Agent 生成几张图片后会显示在这里。")
        return

    cols_per_row = 4
    for i in range(0, len(history), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, entry in enumerate(history[i : i + cols_per_row]):
            with cols[j]:
                st.markdown(f"**#{entry['id']}** · {entry['rating']}")
                if entry["success"] and entry["output_path"]:
                    img_path = Path(entry["output_path"])
                    if img_path.exists():
                        st.image(str(img_path), use_container_width=True)
                    else:
                        st.caption(f"⚠️ 文件缺失: {img_path}")
                else:
                    st.caption("❌ 生成失败")
                prompt_brief = (entry["prompt"] or "")[:80]
                st.caption(prompt_brief)


def _render_status(domain_id: str):
    st.subheader("⚙️ 状态信息")
    try:
        runtime = _get_runtime(domain_id)
    except Exception as e:
        st.error(f"无法初始化 runtime: {e}")
        return

    pack = getattr(runtime, "_domain_pack", None)
    config: ProAgentConfig = runtime.config

    cols = st.columns(2)
    with cols[0]:
        st.markdown("#### 当前 Agent")
        st.json({
            "domain": config.domain,
            "display_name": pack.display_name if pack else "-",
            "max_iterations": getattr(pack, "max_iterations", "-"),
            "max_test_steps": getattr(pack, "max_test_steps", "-"),
            "requires_ssh": pack.requires_ssh if pack else "-",
            "tools": [t.name for t in (pack.get_tools(runtime) if pack else [])],
        })

    with cols[1]:
        st.markdown("#### 模型 & API")
        mc = config.models.executor
        env_var = "MINIMAX_CN_API_KEY"
        api_key_set = bool(os.environ.get(env_var))
        st.json({
            "provider": mc.provider,
            "model": mc.model,
            "base_url": mc.base_url or "(default)",
            f"{env_var} 已配置": api_key_set,
        })

    st.markdown("#### Policy Guard")
    if runtime.policy:
        st.json({
            "domain": runtime.policy.domain,
            "denylist_patterns": len(runtime.policy.config.denylist_patterns),
            "write_action_whitelist": runtime.policy.config.write_action_whitelist,
            "forbidden_tools": runtime.policy.config.forbidden_tools,
        })


if __name__ == "__main__":
    main()
