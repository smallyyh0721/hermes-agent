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
from proagent.storage.phase5 import (
    LayeredMemoryStore,
    SessionHistoryStore,
    SkillDraftStore,
    UsageStore,
    WorkItemStore,
)


# ---- helpers ----------------------------------------------------------------

REPORTS_DIR = PROJECT_ROOT / "proagent" / "storage" / "reports"
AIGC_HISTORY_DB = PROJECT_ROOT / "proagent" / "storage" / "aigc_history.db"
AIGC_OUTPUT_DIR = Path.cwd() / "output" / "aigc"
SESSION_HISTORY_DB = PROJECT_ROOT / "proagent" / "storage" / "session_history.db"
WORK_ITEMS_DB = PROJECT_ROOT / "proagent" / "storage" / "work_items.db"
USAGE_DB = PROJECT_ROOT / "proagent" / "storage" / "usage.db"
SKILL_DRAFTS_DB = PROJECT_ROOT / "proagent" / "storage" / "skill_drafts.db"
MEMORY_DB = PROJECT_ROOT / "proagent" / "storage" / "memory.db"


# Friendly names for the three agents
AGENT_DISPLAY = {
    "server-health-inspector": ("🔧 SRE Agent", "自动诊断 + 定期巡检"),
    "aigc-creator": ("🎨 AIGC Agent", "提示词优化 + 多图生成"),
    "test-agent": ("🧪 Test Agent", "代码扫描 + 测试生成"),
    "develop-agent": ("🛠️ Develop Agent", "需求驱动开发 + 测试交接"),
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


def _build_agent(domain_id: str, memory_user_id: str = "web:local") -> ProAgent:
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
        memory_store=LayeredMemoryStore(MEMORY_DB),
        memory_user_id=memory_user_id,
        session_id=f"web:{memory_user_id}:{domain_id}",
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


def _list_sessions(limit: int = 100, agent_id: str = "") -> List[Dict[str, Any]]:
    return SessionHistoryStore(SESSION_HISTORY_DB).list_sessions(limit=limit, agent_id=agent_id)


def _list_work_items(limit: int = 100) -> List[Dict[str, Any]]:
    return WorkItemStore(WORK_ITEMS_DB).list_work_items(limit=limit)


def _list_usage(limit: int = 100) -> List[Dict[str, Any]]:
    return UsageStore(USAGE_DB).list_usage(limit=limit)


def _usage_totals() -> Dict[str, Any]:
    return UsageStore(USAGE_DB).daily_totals()


def _list_skill_drafts(limit: int = 100) -> List[Dict[str, Any]]:
    return SkillDraftStore(SKILL_DRAFTS_DB).list_drafts(limit=limit)


def _list_memory(layer: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    return LayeredMemoryStore(MEMORY_DB).list_memory(layer=layer, limit=limit)


def _list_user_memory(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return LayeredMemoryStore(MEMORY_DB).list_memory(layer="user", owner_id=user_id, limit=limit)


# ---- UI ---------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="ProAgent 控制中心",
        page_icon="🤖",
        layout="wide",
    )

    st.title("🤖 ProAgent 控制中心")
    st.caption("统一入口：SRE / Test / Develop 状态面板，AIGC 保持 Discord-first")

    # Discover packs once
    available_packs = discover_packs()
    pack_ids = [p["id"] for p in available_packs]

    # ---- sidebar ------------------------------------------------------------
    with st.sidebar:
        st.markdown("### 选择 Agent")
        # Restrict to the three production agents we ship in Phase 4
        ordered = [
            pid for pid in ["server-health-inspector", "test-agent", "develop-agent", "aigc-creator"]
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

        st.text_input(
            "User ID",
            value=st.session_state.get("proagent_user_id", "web:local"),
            key="proagent_user_id",
            help="用于隔离个人 memory。不同 User ID 的 user memory 不会互相注入。",
        )

        for pid in ordered:
            label, desc = AGENT_DISPLAY.get(pid, (pid, ""))
            if pid == selected:
                st.caption(f"**{desc}**")

        st.divider()

        page = st.radio(
            "面板",
            options=[
                "💬 对话",
                "🧾 Session History",
                "🛠️ Develop Board",
                "🧪 Test Dashboard",
                "💰 Token Usage",
                "🧠 Memory",
                "🧩 Skill Drafts",
                "📋 报告库",
                "🖼️ 图片画廊",
                "⚙️ 状态",
            ],
            key="page",
        )

        st.divider()
        st.caption("提示：图片画廊只对 AIGC Agent 有意义；")
        st.caption("报告库展示 SRE 写入的诊断/巡检报告。")

    # ---- main panels --------------------------------------------------------
    if page == "💬 对话":
        _render_chat(selected)
    elif page == "🧾 Session History":
        _render_session_history()
    elif page == "🛠️ Develop Board":
        _render_develop_board()
    elif page == "🧪 Test Dashboard":
        _render_test_dashboard()
    elif page == "💰 Token Usage":
        _render_token_usage()
    elif page == "🧠 Memory":
        _render_memory()
    elif page == "🧩 Skill Drafts":
        _render_skill_drafts()
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
    memory_user_id = st.session_state.get("proagent_user_id", "web:local")
    history_key = f"chat_history_{memory_user_id}_{domain_id}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    # Reset / new conversation button
    cols = st.columns([6, 1])
    with cols[1]:
        if st.button("🔄 新对话", key=f"reset_{domain_id}"):
            st.session_state[history_key] = []
            # Drop cached runtime/agent for this domain to truly reset
            if f"agent_{memory_user_id}_{domain_id}" in st.session_state:
                del st.session_state[f"agent_{memory_user_id}_{domain_id}"]
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
        agent_key = f"agent_{memory_user_id}_{domain_id}"
        if agent_key not in st.session_state:
            try:
                st.session_state[agent_key] = _build_agent(domain_id, memory_user_id=memory_user_id)
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


def _render_session_history():
    st.subheader("🧾 Session History")
    agent_filter = st.selectbox(
        "Agent filter",
        options=["", "sre", "test", "develop", "aigc"],
        format_func=lambda x: "全部" if not x else x,
    )
    sessions = _list_sessions(agent_id=agent_filter)
    if not sessions:
        st.info("暂无持久化 session。Discord gateway 处理消息后会写入这里。")
        return
    st.dataframe(sessions, use_container_width=True, hide_index=True)
    selected = st.selectbox("查看消息", options=[s["session_id"] for s in sessions])
    if selected:
        messages = SessionHistoryStore(SESSION_HISTORY_DB).get_messages(selected)
        events = SessionHistoryStore(SESSION_HISTORY_DB).get_tool_events(selected)
        st.markdown("#### Messages")
        st.dataframe(messages, use_container_width=True, hide_index=True)
        st.markdown("#### Tool Events")
        st.dataframe(events, use_container_width=True, hide_index=True)


def _render_develop_board():
    st.subheader("🛠️ Develop Board")
    items = _list_work_items()
    if not items:
        st.info("暂无 work item。Develop Agent 接收需求后会记录 feature/bugfix 状态。")
        return
    st.dataframe(items, use_container_width=True, hide_index=True)


def _render_test_dashboard():
    st.subheader("🧪 Test Dashboard")
    work_items = _list_work_items()
    test_rows = [
        {
            "item_id": item["item_id"],
            "title": item["title"],
            "implementation_status": item["status"],
            "test_status": item["test_status"],
            "requirement_ref": item["requirement_ref"],
        }
        for item in work_items
    ]
    if test_rows:
        st.dataframe(test_rows, use_container_width=True, hide_index=True)
    else:
        st.info("暂无测试状态。Test Agent 验证 Develop 交付后会显示覆盖情况。")

    reports = [p for p in _list_reports() if "test" in p.name.lower()]
    if reports:
        st.markdown("#### Test Reports")
        st.dataframe(
            [{"name": p.name, "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))} for p in reports],
            use_container_width=True,
            hide_index=True,
        )


def _render_token_usage():
    st.subheader("💰 Token Usage")
    totals = _usage_totals()
    cols = st.columns(3)
    cols[0].metric("Input Tokens", int(totals.get("input_tokens", 0)))
    cols[1].metric("Output Tokens", int(totals.get("output_tokens", 0)))
    cols[2].metric("Estimated Cost", f"{float(totals.get('estimated_cost', 0)):.6f}")

    usage = _list_usage()
    if usage:
        st.dataframe(usage, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 token usage 记录。接入 provider usage 捕获后会持续写入。")


def _render_memory():
    st.subheader("🧠 Layered Memory")
    layer = st.selectbox("Layer", options=["", "user", "lab", "target", "agent"], format_func=lambda x: "全部" if not x else x)
    memory_user_id = st.session_state.get("proagent_user_id", "web:local")
    if layer == "user":
        rows = _list_user_memory(memory_user_id)
        st.caption(f"当前只显示 User ID `{memory_user_id}` 的个人 memory。")
    else:
        rows = _list_memory(layer=layer)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 memory。后续可由 Agent 或导入流程写入 user/lab/target/agent 层记忆。")


def _render_skill_drafts():
    st.subheader("🧩 Skill Drafts")
    rows = _list_skill_drafts()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 skill draft。重复流程或用户要求保存为 skill 后会写入这里。")


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
