"""Phase 5 productization tests.

These tests cover the deployable ProAgent spine: durable stores, agent routing,
Develop Agent discovery, and deployment manifests.
"""

from __future__ import annotations

from pathlib import Path


def test_phase5_stores_persist_sessions_work_items_usage(tmp_path):
    from proagent.storage.phase5 import (
        LayeredMemoryStore,
        SessionHistoryStore,
        SkillDraftStore,
        UsageStore,
        WorkItemStore,
    )

    session_store = SessionHistoryStore(tmp_path / "session_history.db")
    session_id = session_store.start_session(
        agent_id="sre",
        channel_id="discord:ops",
        user_id="u1",
        source="discord",
        status="running",
    )
    session_store.add_message(session_id, "user", "check status")
    session_store.add_tool_event(session_id, "server_shell", {"command": "uptime"}, "ok")
    session_store.finish_session(session_id, status="ok", summary="healthy")

    sessions = session_store.list_sessions()
    assert sessions[0]["session_id"] == session_id
    assert sessions[0]["agent_id"] == "sre"
    assert sessions[0]["summary"] == "healthy"
    assert len(session_store.get_messages(session_id)) == 1
    assert len(session_store.get_tool_events(session_id)) == 1

    work_store = WorkItemStore(tmp_path / "work_items.db")
    item_id = work_store.create_work_item(
        title="Add Discord router",
        kind="feature",
        agent_id="develop",
        requirement_ref="docs/ProAgent-Phase5-Plan.md#M5.3",
    )
    work_store.update_work_item(item_id, status="implemented", test_status="pending")
    assert work_store.list_work_items()[0]["status"] == "implemented"

    usage_store = UsageStore(tmp_path / "usage.db")
    usage_store.record_usage(
        session_id=session_id,
        agent_id="sre",
        provider="openai",
        model="gpt-4.1-mini",
        input_tokens=100,
        output_tokens=25,
        estimated_cost=0.001,
    )
    usage = usage_store.daily_totals()
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 25
    assert usage["estimated_cost"] == 0.001

    draft_store = SkillDraftStore(tmp_path / "skill_drafts.db")
    draft_id = draft_store.create_draft(
        name="disk_pressure_triage",
        description="Diagnose disk pressure safely",
        owner_agent="sre",
        content="# Disk Pressure Triage\n\n## Procedure\n1. df -h\n",
        evidence="session-1",
        tests="dry run only",
    )
    draft_store.update_status(draft_id, "approved")
    assert draft_store.list_drafts()[0]["status"] == "approved"

    memory_store = LayeredMemoryStore(tmp_path / "memory.db")
    memory_store.upsert_memory(
        layer="lab",
        key="topology",
        value="Storage nodes use Ceph and JuiceFS",
        source="docs",
    )
    assert memory_store.search("ceph")[0]["layer"] == "lab"


def test_agent_router_parses_slash_commands_and_channel_defaults(tmp_path):
    from proagent.core.agent_router import AgentRouter
    from proagent.storage.phase5 import SessionHistoryStore, UsageStore, WorkItemStore

    router = AgentRouter(
        session_store=SessionHistoryStore(tmp_path / "session_history.db"),
        work_store=WorkItemStore(tmp_path / "work_items.db"),
        usage_store=UsageStore(tmp_path / "usage.db"),
    )

    routed = router.route_message("/develop fix gateway health", channel_id="c1", user_id="u1")
    assert routed.agent_id == "develop"
    assert routed.domain_id == "develop-agent"
    assert routed.prompt == "fix gateway health"

    switched = router.route_message("/agent switch sre", channel_id="c1", user_id="u1")
    assert switched.control_response
    assert "sre" in switched.control_response

    defaulted = router.route_message("check disk", channel_id="c1", user_id="u1")
    assert defaulted.agent_id == "sre"
    assert defaulted.domain_id == "server-health-inspector"
    assert defaulted.prompt == "check disk"

    status = router.route_message("/agent status", channel_id="c1", user_id="u1")
    assert status.control_response
    assert "channel_default=sre" in status.control_response

    news = router.route_message("/news today's AI and football brief", channel_id="c1", user_id="u1")
    assert news.agent_id == "news"
    assert news.domain_id == "interest-news-agent"
    assert news.prompt == "today's AI and football brief"

    switched_news = router.route_message("/agent switch news", channel_id="c1", user_id="u1")
    assert switched_news.control_response
    assert "news" in switched_news.control_response


def test_develop_agent_pack_is_discoverable_and_local_only():
    from proagent.domain.base import discover_packs, load_pack

    pack_ids = {p["id"] for p in discover_packs()}
    assert "develop-agent" in pack_ids

    pack = load_pack("develop-agent")
    assert pack is not None
    assert pack.requires_ssh is False
    assert pack.get_skills()
    tool_names = {tool.name for tool in pack.get_tools(runtime=None)}
    assert {"code_read", "code_edit", "work_item_create", "work_item_update", "test_delegate"} <= tool_names


def test_interest_news_agent_reuses_hermes_skills_and_exposes_discord_digest_tools():
    import yaml

    from proagent.domain.base import discover_packs, load_pack

    pack_ids = {p["id"] for p in discover_packs()}
    assert "interest-news-agent" in pack_ids

    pack = load_pack("interest-news-agent")
    assert pack is not None
    assert pack.requires_ssh is False

    meta = yaml.safe_load((pack.pack_dir / "pack.yaml").read_text(encoding="utf-8"))
    assert "discord" in meta["gateways"]
    assert "cron" in meta["gateways"]
    assert "optional-skills/devops/watchers/SKILL.md" in meta["skill_refs"]
    assert "optional-skills/research/duckduckgo-search/SKILL.md" in meta["skill_refs"]

    skills = "\n".join(pack.get_skills())
    assert "Watchers" in skills
    assert "DuckDuckGo Search" in skills
    assert "arXiv Research" in skills

    assert "重大国际新闻" in pack.system_prompt
    assert "原文链接" in pack.system_prompt
    tool_names = {tool.name for tool in pack.get_tools(runtime=None)}
    assert {"news_source_catalog", "fetch_feed", "web_news_search", "digest_outline"} <= tool_names


def test_proagent_deployment_manifests_exist_and_use_proagent_entrypoint():
    root = Path(__file__).resolve().parents[2]

    dockerfile = root / "Dockerfile.proagent"
    compose = root / "docker-compose.proagent.yml"
    env_example = root / ".env.proagent.example"

    assert dockerfile.exists()
    assert compose.exists()
    assert env_example.exists()

    docker_text = dockerfile.read_text(encoding="utf-8")
    compose_text = compose.read_text(encoding="utf-8")
    env_text = env_example.read_text(encoding="utf-8")

    assert "proagent_run.py" in docker_text
    assert "HEALTHCHECK" in docker_text
    assert "proagent-gateway" in compose_text
    assert "proagent-web" in compose_text
    assert "DISCORD_BOT_TOKEN" in env_text
    assert "MINIMAX_CN_API_KEY" in env_text


def test_proagent_records_provider_usage_from_response(tmp_path, monkeypatch):
    from proagent.core.agent import Message, ProAgent
    from proagent.storage.phase5 import UsageStore

    usage_store = UsageStore(tmp_path / "usage.db")

    agent = ProAgent.__new__(ProAgent)
    agent.provider = "openai"
    agent.model = "gpt-test"
    agent.usage_store = usage_store
    agent.session_id = "session-1"
    agent.agent_id = "sre"

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7

    class Response:
        usage = Usage()

    agent._record_usage(Response())
    rows = usage_store.list_usage()
    assert rows[0]["session_id"] == "session-1"
    assert rows[0]["input_tokens"] == 11
    assert rows[0]["output_tokens"] == 7


def test_skill_draft_can_be_enabled_to_domain_pack(tmp_path):
    from proagent.storage.phase5 import SkillDraftStore, enable_skill_draft

    db = tmp_path / "skill_drafts.db"
    pack_dir = tmp_path / "domain" / "server_health_inspector"
    draft_store = SkillDraftStore(db)
    draft_id = draft_store.create_draft(
        name="GPU Temperature Monitor",
        description="Check GPU temperature",
        owner_agent="sre",
        content="# GPU Temperature Monitor\n\n## When to use\nGPU alerts\n",
        evidence="session gpu-1",
        tests="manual dry-run",
    )
    enabled_path = enable_skill_draft(draft_store, draft_id, pack_dir)
    assert enabled_path.exists()
    assert enabled_path.name == "gpu_temperature_monitor.md"
    assert draft_store.get_draft(draft_id)["status"] == "enabled"


def test_archive_plan_exists_and_lists_validation_commands():
    root = Path(__file__).resolve().parents[2]
    archive_plan = root / "docs" / "Hermes-Archive-Plan.md"
    assert archive_plan.exists()
    text = archive_plan.read_text(encoding="utf-8")
    assert "Validation commands" in text
    assert "proagent/tests/test_phase5_productization.py" in text


def test_discord_gateway_registers_agent_control_slash_group():
    root = Path(__file__).resolve().parents[2]
    cli_main = root / "proagent" / "cli" / "main.py"
    text = cli_main.read_text(encoding="utf-8")

    assert 'discord.app_commands.Group(\n        name="agent"' in text
    assert '@agent_group.command(name="status"' in text
    assert '@agent_group.command(name="usage"' in text
    assert '@agent_group.command(name="switch"' in text
    assert "tree.add_command(agent_group)" in text


def test_proagent_gateway_defaults_to_feishu_when_enabled():
    from proagent.cli.main import _resolve_gateway_platform
    from proagent.core.config import GatewayConfig, ProAgentConfig

    config = ProAgentConfig()
    config.gateways["feishu"] = GatewayConfig(enabled=True, settings={})
    config.gateways["discord"] = GatewayConfig(enabled=False, settings={})

    assert _resolve_gateway_platform(config) == "feishu"


def test_proagent_builds_feishu_platform_config_from_yaml_and_env(monkeypatch):
    from gateway.config import PlatformConfig
    from proagent.cli.main import _build_feishu_platform_config
    from proagent.core.config import GatewayConfig, ProAgentConfig

    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_test")

    config = ProAgentConfig()
    config.gateways["feishu"] = GatewayConfig(
        enabled=True,
        settings={
            "enabled": True,
            "app_id": "${FEISHU_APP_ID}",
            "app_secret": "${FEISHU_APP_SECRET}",
            "domain": "feishu",
            "connection_mode": "websocket",
        },
    )

    platform_config = _build_feishu_platform_config(config)

    assert isinstance(platform_config, PlatformConfig)
    assert platform_config.enabled is True
    assert platform_config.extra["app_id"] == "cli_test"
    assert platform_config.extra["app_secret"] == "secret_test"
    assert platform_config.extra["domain"] == "feishu"
    assert platform_config.extra["connection_mode"] == "websocket"


def test_user_memory_is_isolated_by_owner_id(tmp_path):
    from proagent.storage.phase5 import LayeredMemoryStore

    store = LayeredMemoryStore(tmp_path / "memory.db")
    store.upsert_memory("user", "report_format", "Use Chinese markdown", owner_id="discord:u1")
    store.upsert_memory("user", "report_format", "Use terse English bullets", owner_id="discord:u2")

    u1 = store.search_for_user("report", owner_id="discord:u1")
    u2 = store.search_for_user("report", owner_id="discord:u2")

    assert len(u1) == 1
    assert len(u2) == 1
    assert u1[0]["value"] == "Use Chinese markdown"
    assert u2[0]["value"] == "Use terse English bullets"


def test_proagent_injects_only_current_user_memory(tmp_path):
    from proagent.core.agent import Message, ProAgent
    from proagent.storage.phase5 import LayeredMemoryStore

    store = LayeredMemoryStore(tmp_path / "memory.db")
    store.upsert_memory("user", "customer_pref", "Always include acceptance criteria", owner_id="discord:u1")
    store.upsert_memory("user", "customer_pref", "Never mention acceptance criteria", owner_id="discord:u2")

    agent = ProAgent(
        provider="openai",
        model="test-model",
        system_prompt="Base prompt",
        api_key="test",
        memory_store=store,
        memory_user_id="discord:u1",
    )
    agent.messages.append(Message(role="user", content="What are the customer preferences?"))

    prompt = agent._system_prompt_with_memory()
    assert "Always include acceptance criteria" in prompt
    assert "Never mention acceptance criteria" not in prompt


def test_proagent_memory_tools_are_user_scoped(tmp_path):
    from proagent.core.agent import ProAgent
    from proagent.storage.phase5 import LayeredMemoryStore

    store = LayeredMemoryStore(tmp_path / "memory.db")
    agent = ProAgent(
        provider="openai",
        model="test-model",
        system_prompt="Base prompt",
        api_key="test",
        memory_store=store,
        memory_user_id="discord:u1",
        session_id="s1",
    )

    assert "memory_remember" in {tool.name for tool in agent.tools}
    assert "Stored user memory" in agent._execute_tool(
        {"name": "memory_remember", "arguments": {"key": "tone", "value": "Prefer direct Chinese summaries"}}
    )
    assert "Prefer direct Chinese summaries" in agent._execute_tool(
        {"name": "memory_search", "arguments": {"query": "tone"}}
    )
    assert store.search_for_user("tone", owner_id="discord:u2") == []
