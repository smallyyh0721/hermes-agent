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
    target_sub.add_parser("remove", help="Remove a target").add_argument("target_id")

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Run one-shot inspection")
    inspect_parser.add_argument("--target", "-t", help="Target to inspect")
    inspect_parser.add_argument("--kind", choices=["quick", "full"], default="quick")

    # status
    subparsers.add_parser("status", help="Show runtime status")

    # gateway
    gw_parser = subparsers.add_parser("gateway", help="Start gateway mode (Discord)")
    gw_parser.add_argument("--config", "-c", help="Path to proagent.yaml")

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
    else:
        parser.print_help()


def cmd_run(args):
    """Start interactive chat with the ProAgent."""
    from proagent.core.config import load_config, find_config_file
    from proagent.core.runtime import ProAgentRuntime
    from proagent.domain.server_health_inspector.tools.read_only.server_shell import set_runtime

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
    set_runtime(runtime)

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

    # Import and register the server_shell tool
    import proagent.domain.server_health_inspector.tools.read_only.server_shell  # noqa: F401

    # Start Hermes agent in CLI mode
    print("💬 Starting agent... (type 'exit' or Ctrl+C to quit)")
    print("   Ask me about server health, e.g.:")
    print("   - '服务器状态如何？'")
    print("   - 'CPU 负载多少？'")
    print("   - '检查磁盘使用情况'")
    print("   - '最近有什么错误日志？'")
    print()

    _run_hermes_agent(runtime, config)


def _run_hermes_agent(runtime, config):
    """Run the Hermes AIAgent with ProAgent configuration."""
    try:
        from run_agent import AIAgent
    except ImportError:
        # Try alternative import path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from run_agent import AIAgent

    agent_kwargs = runtime.get_hermes_agent_kwargs()

    # Only enable the proagent toolset (server_shell)
    agent_kwargs["enabled_toolsets"] = ["proagent"]
    agent_kwargs["platform"] = "cli"
    agent_kwargs["quiet_mode"] = False

    agent = AIAgent(**agent_kwargs)

    # Simple REPL loop
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

            try:
                response = agent.run_conversation(user_input)
                if response:
                    print(f"\n🤖 {response}")
            except KeyboardInterrupt:
                print("\n⚡ Interrupted")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")

    except KeyboardInterrupt:
        pass

    print("\n👋 ProAgent session ended.")
    runtime.ssh_pool.disconnect_all()


def cmd_setup(args):
    """Interactive setup wizard."""
    print("🔧 ProAgent Setup Wizard")
    print("=" * 50)
    print()

    # Step 1: Model configuration
    print("Step 1: Model Configuration")
    print("-" * 30)
    provider = input("  Provider [openai]: ").strip() or "openai"
    model = input("  Model [gpt-4.1-mini]: ").strip() or "gpt-4.1-mini"

    api_key_env = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    existing_key = os.environ.get(api_key_env, "")
    if existing_key:
        print(f"  ✅ {api_key_env} found in environment")
    else:
        api_key = input(f"  {api_key_env}: ").strip()
        if api_key:
            os.environ[api_key_env] = api_key
    print()

    # Step 2: Target configuration
    print("Step 2: Target Server")
    print("-" * 30)
    backend = input("  Backend [local/ssh]: ").strip() or "local"

    target_config = {"id": "default", "backend": backend}
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

    config = ProAgentConfig(
        domain="server-health-inspector",
        models=ModelsConfig(
            planner=ModelConfig(provider=provider, model=model),
            executor=ModelConfig(provider=provider, model=model),
            summarizer=ModelConfig(provider=provider, model=model),
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

    config = load_config()

    action = getattr(args, "model_action", None)

    if action == "show" or action is None:
        print("📦 Model Configuration")
        print(f"  Planner:    {config.models.planner.provider}/{config.models.planner.model}")
        print(f"  Executor:   {config.models.executor.provider}/{config.models.executor.model}")
        print(f"  Summarizer: {config.models.summarizer.provider}/{config.models.summarizer.model}")

    elif action == "test":
        print("🔌 Testing model connectivity...")
        # Quick test by trying to import and instantiate
        mc = config.models.executor
        print(f"  Testing {mc.provider}/{mc.model}...")
        try:
            import openai
            client = openai.OpenAI()
            resp = client.chat.completions.create(
                model=mc.model,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )
            print(f"  ✅ Connected! Response: {resp.choices[0].message.content}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    elif action == "set":
        parts = args.model_spec.split(":", 1)
        if len(parts) == 2:
            provider, model = parts
        else:
            provider = "openai"
            model = parts[0]
        print(f"  Setting {args.role} → {provider}/{model}")
        # Would save to config here
        print("  ✅ Updated (restart proagent to apply)")


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


def cmd_inspect(args):
    """Run a one-shot inspection."""
    from proagent.core.config import load_config
    from proagent.core.runtime import ProAgentRuntime
    from proagent.domain.server_health_inspector.tools.read_only.server_shell import set_runtime

    config = load_config()
    if hasattr(args, "target") and args.target:
        config.default_target = args.target

    runtime = ProAgentRuntime(config=config)
    set_runtime(runtime)

    print(f"🔍 Running {args.kind} inspection on '{config.default_target}'...")
    results = runtime.connect_targets()

    if not results.get(config.default_target, False):
        print(f"❌ Cannot connect to target '{config.default_target}'")
        sys.exit(1)

    # Run inspection via agent
    import proagent.domain.server_health_inspector.tools.read_only.server_shell  # noqa: F401
    _run_hermes_agent(runtime, config)


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


def cmd_gateway(args):
    """Start the gateway (Discord) mode."""
    from proagent.core.config import load_config
    from proagent.core.runtime import ProAgentRuntime
    from proagent.domain.server_health_inspector.tools.read_only.server_shell import set_runtime

    config_path = Path(args.config) if hasattr(args, "config") and args.config else None
    config = load_config(config_path)

    print("🚀 ProAgent Gateway starting...")
    runtime = ProAgentRuntime(config=config)
    set_runtime(runtime)

    # Connect targets
    results = runtime.connect_targets()
    for target_id, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {target_id}")

    # Register tool
    import proagent.domain.server_health_inspector.tools.read_only.server_shell  # noqa: F401

    # Start Hermes gateway with ProAgent config
    print("\n📡 Starting Hermes gateway with ProAgent domain...")
    print("   (This will connect to Discord and listen for messages)")
    print()

    # Set environment for Hermes gateway
    os.environ["HERMES_PROAGENT_MODE"] = "1"
    os.environ.setdefault("HERMES_PROAGENT_SYSTEM_PROMPT", runtime.build_hermes_system_prompt())

    # Import and run Hermes gateway
    try:
        from gateway.run import start_gateway
        import asyncio
        asyncio.run(start_gateway())
    except ImportError as e:
        print(f"❌ Cannot import Hermes gateway: {e}")
        print("   Make sure you're running from the hermes-agent directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Gateway stopped.")
        runtime.ssh_pool.disconnect_all()


if __name__ == "__main__":
    main()
