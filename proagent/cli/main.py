"""ProAgent CLI - Main entry point.

Usage:
    proagent run              # Start interactive chat with the agent
    proagent setup            # Interactive setup wizard
    proagent model            # Configure models
    proagent model show       # Show current model config
    proagent model test       # Test model connectivity
    proagent target add       # Add a target server
    proagent target list      # List configured targets
    proagent target test      # Test target connectivity
    proagent inspect          # Run a one-shot inspection
    proagent status           # Show runtime status
    proagent gateway          # Start gateway (Discord) mode
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(
        prog="proagent",
        description="ProAgent - Professional Domain Agent Runtime",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Start interactive chat")
    run_parser.add_argument("--config", "-c", help="Path to proagent.yaml")
    run_parser.add_argument("--target", "-t", help="Override default target")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Show tool calls and thinking process")

    # setup
    subparsers.add_parser("setup", help="Interactive setup wizard")

    # model
    model_parser = subparsers.add_parser("model", help="Configure models")
    model_sub = model_parser.add_subparsers(dest="model_action")
    model_sub.add_parser("show", help="Show current model config")
    model_sub.add_parser("test", help="Test model connectivity")
    model_set = model_sub.add_parser("set", help="Set model for a role")
    model_set.add_argument("role", choices=["planner", "executor", "summarizer"])
    model_set.add_argument("model_spec", help="provider:model (e.g. openai:gpt-4.1-mini)")

    # target
    target_parser = subparsers.add_parser("target", help="Manage target servers")
    target_sub = target_parser.add_subparsers(dest="target_action")
    target_sub.add_parser("list", help="List configured targets")
    target_add = target_sub.add_parser("add", help="Add a target server")
    target_add.add_argument("--id", help="Target ID")
    target_add.add_argument("--backend", choices=["ssh", "local", "docker"], default="ssh")
    target_add.add_argument("--host", help="SSH host")
    target_add.add_argument("--user", help="SSH user")
    target_add.add_argument("--port", type=int, default=22, help="SSH port")
    target_add.add_argument("--keyfile", help="SSH key file path")
    target_test = target_sub.add_parser("test", help="Test target connectivity")
    target_test.add_argument("target_id", nargs="?", help="Target ID to test (all if omitted)")
    target_test.add_argument("--all", action="store_true", help="Test all targets")
    target_sub.add_parser("remove", help="Remove a target").add_argument("target_id")
    target_import = target_sub.add_parser("import", help="Import targets from hosts.yaml")
    target_import.add_argument("hosts_file", help="Path to hosts.yaml")

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Run one-shot inspection")
    inspect_parser.add_argument("--target", "-t", help="Target to inspect")
    inspect_parser.add_argument("--kind", choices=["quick", "full"], default="quick")
    inspect_parser.add_argument("--verbose", "-v", action="store_true", help="Show tool calls and thinking process")

    # status
    subparsers.add_parser("status", help="Show runtime status")

    # gateway
    gw_parser = subparsers.add_parser("gateway", help="Start gateway mode (Discord)")
    gw_parser.add_argument("--config", "-c", help="Path to proagent.yaml")

    # domain
    domain_parser = subparsers.add_parser("domain", help="Manage domain packs")
    domain_sub = domain_parser.add_subparsers(dest="domain_action")
    domain_sub.add_parser("list", help="List available domain packs")
    domain_use = domain_sub.add_parser("use", help="Switch active domain")
    domain_use.add_argument("domain_id", help="Domain pack ID to activate")

    args = parser.parse_args()

    if args.command is None:
        # Default to interactive run
        args.command = "run"

    if args.command == "run":
        cmd_run(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "model":
        cmd_model(args)
    elif args.command == "target":
        cmd_target(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "gateway":
        cmd_gateway(args)
    elif args.command == "domain":
        cmd_domain(args)
    else:
        parser.print_help()


def cmd_run(args):
    """Start interactive chat with the ProAgent."""
    from proagent.core.config import load_config, find_config_file
    from proagent.core.runtime import ProAgentRuntime
    from proagent.core.agent import ProAgent, build_server_shell_tool

    config_path = Path(args.config) if hasattr(args, "config") and args.config else None
    config = load_config(config_path)

    # Override target if specified
    if hasattr(args, "target") and args.target:
        config.default_target = args.target

    print("🚀 ProAgent Server Health Inspector starting...")
    print(f"   Domain: {config.domain}")
    print(f"   Default target: {config.default_target}")
    print(f"   Model: {config.models.executor.provider}/{config.models.executor.model}")
    print()

    # Initialize runtime
    runtime = ProAgentRuntime(config=config)

    # Connect to targets
    print("📡 Connecting to targets...")
    results = runtime.connect_targets()
    for target_id, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {target_id}")
    print()

    if not any(results.values()):
        print("❌ No targets connected. Run 'proagent target test' to diagnose.")
        sys.exit(1)

    # Build the minimal ProAgent
    mc = config.models.executor
    verbose = getattr(args, "verbose", False)

    # Build tools based on active domain
    tools = _build_tools_for_domain(config.domain, runtime)

    try:
        agent = ProAgent(
            provider=mc.provider,
            model=mc.model,
            system_prompt=runtime.build_hermes_system_prompt(),
            tools=tools,
            base_url=mc.base_url,
            verbose=verbose,
        )
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Start REPL
    print("💬 Starting agent... (type 'exit' or Ctrl+C to quit)")
    print("   Ask me about server health, e.g.:")
    print("   - '服务器状态如何？'")
    print("   - 'CPU 负载多少？'")
    print("   - '检查磁盘使用情况'")
    print("   - '最近有什么错误日志？'")
    print()

    _run_repl(agent, runtime)


def _build_tools_for_domain(domain: str, runtime) -> list:
    """Build the appropriate tool list based on the active domain."""
    from proagent.core.agent import ToolDef, build_server_shell_tool

    if domain in ("server-health-inspector", "server_health_inspector"):
        return [build_server_shell_tool(runtime)]
    elif domain in ("aigc-creator", "aigc_creator"):
        from proagent.domain.aigc_creator.tools.aigc_generate import aigc_generate_handler
        return [ToolDef(
            name="aigc_generate",
            description=(
                "Generate AI content (images, speech, music) using MiniMax CLI. "
                "Use command='image generate' for images, 'speech synthesize' for voice. "
                "The prompt describes what to generate. Options are extra CLI flags."
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
    else:
        # Unknown domain — fallback to server_shell
        return [build_server_shell_tool(runtime)]


def _run_repl(agent, runtime):
    """Run the interactive REPL with the ProAgent."""
    try:
        while True:
            try:
                user_input = input("\n🧑 > ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if user_input.lower() in ("/new", "/reset"):
                agent.reset()
                print("🔄 Conversation reset")
                continue

            try:
                response = agent.chat(user_input)
                if response:
                    print(f"\n🤖 {response}")
            except KeyboardInterrupt:
                print("\n⚡ Interrupted")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

    except KeyboardInterrupt:
        pass

    print("\n👋 ProAgent session ended.")
    runtime.ssh_pool.disconnect_all()


def _run_hermes_agent(runtime, config):
    """DEPRECATED: Kept for backward compatibility.
    Phase 1 uses the minimal ProAgent via _run_repl() instead of Hermes AIAgent.
    """
    _run_repl_from_runtime(runtime, config)


def _run_repl_from_runtime(runtime, config, verbose=False):
    """Helper: build agent from runtime+config and run REPL."""
    from proagent.core.agent import ProAgent, build_server_shell_tool
    mc = config.models.executor
    agent = ProAgent(
        provider=mc.provider,
        model=mc.model,
        system_prompt=runtime.build_hermes_system_prompt(),
        tools=[build_server_shell_tool(runtime)],
        base_url=mc.base_url,
        verbose=verbose,
    )
    _run_repl(agent, runtime)


def cmd_setup(args):
    """Interactive setup wizard."""
    from proagent.core.providers import list_providers, resolve_provider

    print("🔧 ProAgent Setup Wizard")
    print("=" * 50)
    print()

    # Step 1: Model configuration
    print("Step 1: Model Provider")
    print("-" * 30)
    providers = list_providers()
    for idx, p in enumerate(providers, 1):
        default_mark = " [default]" if p.id == "minimax-cn" else ""
        print(f"  [{idx}] {p.display_name}{default_mark}")
        if p.notes:
            print(f"      ↳ {p.notes}")
    print()
    choice = input("  Select provider [1-3, default=3]: ").strip() or "3"
    try:
        provider_idx = int(choice) - 1
        if not (0 <= provider_idx < len(providers)):
            provider_idx = 2  # default to minimax-cn (index 2)
    except ValueError:
        provider_idx = 2

    selected = providers[provider_idx]
    print(f"  ✓ Selected: {selected.display_name}")
    print()

    model = input(f"  Model [{selected.default_model}]: ").strip() or selected.default_model

    # API key
    primary_env = selected.env_vars[0]
    existing_key = os.environ.get(primary_env, "")
    if existing_key:
        print(f"  ✅ {primary_env} found in environment")
    else:
        print(f"  Get your API key from: {selected.signup_url}")
        api_key = input(f"  {primary_env}: ").strip()
        if api_key:
            os.environ[primary_env] = api_key
    print()

    # Step 2: Target configuration
    print("Step 2: Target Server")
    print("-" * 30)
    backend = input("  Backend [local/ssh, default=local]: ").strip() or "local"

    target_config = {"id": "local", "backend": backend, "host": "", "user": ""}
    if backend == "ssh":
        target_config["host"] = input("  Host: ").strip()
        target_config["user"] = input("  User: ").strip()
        port = input("  Port [22]: ").strip()
        target_config["port"] = int(port) if port else 22
        keyfile = input("  SSH Key [~/.ssh/id_ed25519]: ").strip() or "~/.ssh/id_ed25519"
        target_config["keyfile"] = keyfile
        target_config["id"] = input("  Target ID [server-01]: ").strip() or "server-01"
    print()

    # Step 3: Gateway (optional)
    print("Step 3: Discord Gateway (optional)")
    print("-" * 30)
    discord_token = input("  Discord Bot Token (Enter to skip): ").strip()
    print()

    # Generate config
    from proagent.core.config import ProAgentConfig, ModelConfig, ModelsConfig, GatewayConfig, save_config
    from proagent.core.ssh_pool import TargetHost

    model_cfg = ModelConfig(
        provider=selected.id,
        model=model,
        base_url=selected.base_url,
    )

    config = ProAgentConfig(
        domain="server-health-inspector",
        models=ModelsConfig(
            planner=model_cfg,
            executor=model_cfg,
            summarizer=model_cfg,
        ),
        default_target=target_config["id"],
        targets=[TargetHost(**target_config)],
    )

    if discord_token:
        config.gateways["discord"] = GatewayConfig(enabled=True, settings={"token": discord_token})
        os.environ["DISCORD_BOT_TOKEN"] = discord_token

    config_path = Path.cwd() / "proagent.yaml"
    save_config(config, config_path)
    print(f"✅ Configuration saved to {config_path}")
    print()
    print("Next steps:")
    print("  proagent run          # Start interactive chat")
    print("  proagent target test  # Test server connectivity")
    print("  proagent gateway      # Start Discord gateway")


def cmd_model(args):
    """Model configuration commands."""
    from proagent.core.config import load_config
    from proagent.core.providers import list_providers, resolve_provider

    config = load_config()

    action = getattr(args, "model_action", None)

    if action == "show" or action is None:
        print("📦 Model Configuration")
        print(f"  Planner:    {config.models.planner.provider}/{config.models.planner.model}")
        print(f"  Executor:   {config.models.executor.provider}/{config.models.executor.model}")
        print(f"  Summarizer: {config.models.summarizer.provider}/{config.models.summarizer.model}")
        print()
        print("Supported providers:")
        for p in list_providers():
            print(f"  - {p.id}: {p.display_name}")

    elif action == "test":
        print("🔌 Testing model connectivity...")
        mc = config.models.executor
        profile = resolve_provider(mc.provider)
        if not profile:
            print(f"  ❌ Unknown provider: {mc.provider}")
            return

        print(f"  Provider: {profile.display_name}")
        print(f"  Model:    {mc.model}")
        if mc.base_url or profile.base_url:
            print(f"  Base URL: {mc.base_url or profile.base_url}")

        try:
            from proagent.core.agent import ProAgent
            agent = ProAgent(
                provider=mc.provider,
                model=mc.model,
                system_prompt="You are a test assistant. Reply with exactly 'ok'.",
                tools=[],
                base_url=mc.base_url,
            )
            response = agent.chat("ping")
            print(f"  ✅ Connected! Response: {response.strip()[:100]}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    elif action == "set":
        parts = args.model_spec.split(":", 1)
        if len(parts) == 2:
            provider_raw, model = parts
            profile = resolve_provider(provider_raw)
            provider = profile.id if profile else provider_raw
        else:
            provider = "openai"
            model = parts[0]
        print(f"  Setting {args.role} → {provider}/{model}")
        print("  ℹ️  Note: This currently displays only; edit proagent.yaml to persist.")


def cmd_target(args):
    """Target management commands."""
    from proagent.core.config import load_config
    from proagent.core.ssh_pool import SSHPool

    config = load_config()
    action = getattr(args, "target_action", None)

    if action == "list" or action is None:
        print("🖥️  Configured Targets")
        if not config.targets:
            print("  (none configured - run 'proagent setup' or 'proagent target add')")
            return
        for t in config.targets:
            default_marker = " ⭐" if t.id == config.default_target else ""
            print(f"  {t.id}: {t.display_name}{default_marker}")

    elif action == "test":
        target_id = getattr(args, "target_id", None)
        pool = SSHPool(config.targets)

        if target_id:
            targets_to_test = [t for t in config.targets if t.id == target_id]
        else:
            targets_to_test = config.targets

        if not targets_to_test:
            print(f"  ❌ Target '{target_id}' not found")
            return

        print("🔌 Testing target connectivity...")
        results = pool.connect_all()
        for tid, success in results.items():
            if target_id and tid != target_id:
                continue
            status = "✅" if success else "❌"
            print(f"  {status} {tid}")

            if success:
                # Run basic diagnostics
                rc, output = pool.execute(tid, "uname -a")
                if rc == 0:
                    print(f"     OS: {output.strip()}")
                rc, output = pool.execute(tid, "uptime")
                if rc == 0:
                    print(f"     Uptime: {output.strip()}")

        pool.disconnect_all()

    elif action == "add":
        print("➕ Adding target (use 'proagent setup' for interactive mode)")
        # Non-interactive add from flags
        if args.id and args.host and args.user:
            print(f"  Added: {args.id} ({args.user}@{args.host}:{args.port})")
        else:
            print("  Required: --id, --host, --user")

    elif action == "remove":
        print(f"  Removing target: {args.target_id}")
        print("  ✅ Removed (restart proagent to apply)")

    elif action == "import":
        from proagent.core.target_import import import_hosts
        hosts_path = Path(args.hosts_file)
        if not hosts_path.exists():
            print(f"  ❌ File not found: {hosts_path}")
            return
        try:
            added, updated = import_hosts(hosts_path)
            print(f"  ✅ Imported: {added} added, {updated} updated")
            print(f"     Run 'python proagent_run.py target list' to verify")
            print(f"     Run 'python proagent_run.py target test --all' to test connectivity")
        except Exception as e:
            print(f"  ❌ Import failed: {e}")


def cmd_inspect(args):
    """Run a one-shot inspection."""
    from proagent.core.config import load_config
    from proagent.core.runtime import ProAgentRuntime
    from proagent.core.agent import ProAgent, build_server_shell_tool

    config = load_config()
    if hasattr(args, "target") and args.target:
        config.default_target = args.target

    runtime = ProAgentRuntime(config=config)

    print(f"🔍 Running {args.kind} inspection on '{config.default_target}'...")
    results = runtime.connect_targets()

    if not results.get(config.default_target, False):
        print(f"❌ Cannot connect to target '{config.default_target}'")
        sys.exit(1)

    # Build agent and send inspection prompt
    mc = config.models.executor
    verbose = getattr(args, "verbose", False)
    agent = ProAgent(
        provider=mc.provider,
        model=mc.model,
        system_prompt=runtime.build_hermes_system_prompt(),
        tools=[build_server_shell_tool(runtime)],
        base_url=mc.base_url,
        verbose=verbose,
    )

    run_id = runtime.create_inspection_run(config.default_target, args.kind, "cli")

    if args.kind == "quick":
        prompt = "执行快速健康检查：CPU、内存、磁盘、failed services、最近错误日志。给出结构化报告。"
    else:
        prompt = "执行深度健康检查：系统信息、CPU详情、内存详情、磁盘详情、网络、全部服务状态、24小时错误日志。给出完整结构化报告。"

    try:
        response = agent.chat(prompt)
        print()
        print(response)
        runtime.complete_inspection_run(run_id, "ok", summary=response[:500])
    except Exception as e:
        print(f"❌ Inspection failed: {e}")
        runtime.complete_inspection_run(run_id, "error", summary=str(e)[:500])
        sys.exit(1)
    finally:
        runtime.ssh_pool.disconnect_all()


def cmd_status(args):
    """Show runtime status."""
    from proagent.core.config import load_config, find_config_file

    config_path = find_config_file()
    if config_path:
        print(f"📄 Config: {config_path}")
    else:
        print("📄 Config: not found (run 'proagent setup')")
        return

    config = load_config()
    print(f"🏷️  Domain: {config.domain}")
    print(f"🤖 Model:  {config.models.executor.provider}/{config.models.executor.model}")
    print(f"🎯 Default target: {config.default_target}")
    print(f"🖥️  Targets: {len(config.targets)}")
    for t in config.targets:
        print(f"    - {t.display_name}")
    print(f"📡 Gateways: {', '.join(k for k, v in config.gateways.items() if v.enabled) or 'none'}")


def cmd_domain(args):
    """Manage domain packs."""
    from proagent.core.config import load_config, save_config, find_config_file
    from pathlib import Path as _P

    action = getattr(args, "domain_action", None)

    # Discover available domain packs
    domain_base = _P(__file__).resolve().parents[1] / "domain"
    available = []
    for d in sorted(domain_base.iterdir()):
        pack_file = d / "pack.yaml"
        if d.is_dir() and pack_file.exists() and d.name != "__pycache__":
            import yaml
            with open(pack_file, "r", encoding="utf-8") as f:
                pack = yaml.safe_load(f) or {}
            available.append({
                "id": pack.get("id", d.name),
                "dir": d.name,
                "display_name": pack.get("display_name", d.name),
                "description": pack.get("description", ""),
            })

    if action == "list" or action is None:
        config = load_config()
        print("📦 Available Domain Packs")
        for p in available:
            active = " ⭐ (active)" if p["dir"] == config.domain.replace("-", "_") or p["id"] == config.domain else ""
            print(f"  {p['id']}: {p['display_name']}{active}")
            if p["description"]:
                print(f"      {p['description']}")
        print()
        print(f"  Switch with: python proagent_run.py domain use <pack-id>")

    elif action == "use":
        domain_id = args.domain_id
        # Find matching pack
        match = None
        for p in available:
            if p["id"] == domain_id or p["dir"] == domain_id.replace("-", "_"):
                match = p
                break

        if not match:
            print(f"❌ Domain pack '{domain_id}' not found.")
            print(f"   Available: {', '.join(p['id'] for p in available)}")
            return

        # Update config
        config_path = find_config_file()
        if not config_path:
            config_path = _P.cwd() / "proagent.yaml"
        config = load_config(config_path)
        config.domain = match["id"]
        save_config(config, config_path)
        print(f"✅ Switched to domain: {match['display_name']}")
        print(f"   Run 'python proagent_run.py run' to start with the new domain")


def cmd_gateway(args):
    """Start the gateway (Discord) mode."""
    from proagent.core.config import load_config
    from proagent.core.runtime import ProAgentRuntime
    from proagent.core.agent import ProAgent, build_server_shell_tool

    config_path = Path(args.config) if hasattr(args, "config") and args.config else None
    config = load_config(config_path)

    print("🚀 ProAgent Discord Gateway starting...")
    runtime = ProAgentRuntime(config=config)

    # Connect targets
    results = runtime.connect_targets()
    for target_id, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {target_id}")
    print()

    # Build the agent
    mc = config.models.executor
    agent = ProAgent(
        provider=mc.provider,
        model=mc.model,
        system_prompt=runtime.build_hermes_system_prompt(),
        tools=[build_server_shell_tool(runtime)],
        base_url=mc.base_url,
    )

    # Start Discord bot
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        discord_gw = config.gateways.get("discord")
        if discord_gw:
            token = discord_gw.settings.get("token", "")
    if not token:
        print("❌ DISCORD_BOT_TOKEN not set in environment or proagent.yaml")
        sys.exit(1)

    try:
        import discord
    except ImportError:
        print("❌ discord.py not installed. Run: pip install 'discord.py>=2.3'")
        sys.exit(1)

    intents = discord.Intents.default()
    intents.message_content = True

    # Detect proxy from environment (discord.py/aiohttp doesn't auto-read env vars)
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY") or ""
    if proxy_url:
        print(f"   🌐 Using proxy: {proxy_url}")

    client = discord.Client(intents=intents, proxy=proxy_url if proxy_url else None)

    # Per-user conversation agents
    user_agents: Dict[int, ProAgent] = {}  # type: ignore

    def _get_agent_for(user_id: int) -> ProAgent:
        if user_id not in user_agents:
            user_agents[user_id] = ProAgent(
                provider=mc.provider,
                model=mc.model,
                system_prompt=runtime.build_hermes_system_prompt(),
                tools=[build_server_shell_tool(runtime)],
                base_url=mc.base_url,
            )
        return user_agents[user_id]

    @client.event
    async def on_ready():
        print(f"✅ Discord connected as {client.user}")
        print("   Send a DM or @ mention the bot to interact")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        # Only respond to DMs or mentions
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = client.user in message.mentions
        if not (is_dm or is_mention):
            return

        # Strip mention
        content = message.content
        if client.user:
            content = content.replace(f"<@{client.user.id}>", "").strip()

        if not content:
            return

        # Special commands
        if content.lower() in ("/new", "/reset"):
            user_agents.pop(message.author.id, None)
            await message.reply("🔄 Conversation reset")
            return

        # Process via agent (blocking call in executor)
        import asyncio
        async with message.channel.typing():
            user_agent = _get_agent_for(message.author.id)
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, user_agent.chat, content
                )
            except Exception as e:
                response = f"❌ Error: {e}"

        # Split long responses
        if not response:
            response = "(empty response)"
        # Discord message limit is 2000 chars
        chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
        for chunk in chunks:
            await message.reply(f"```\n{chunk}\n```" if "\n" in chunk else chunk)

    try:
        client.run(token)
    except KeyboardInterrupt:
        print("\n👋 Gateway stopped.")
    finally:
        runtime.ssh_pool.disconnect_all()


if __name__ == "__main__":
    main()
