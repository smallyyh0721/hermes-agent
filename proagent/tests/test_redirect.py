"""Test redirect pattern fix - allow 2>/dev/null, block writes to real files."""
from pathlib import Path

from proagent.policy.guard import PolicyGuard, load_policy, Decision

policy_path = Path(__file__).resolve().parents[1] / "domain" / "server_health_inspector" / "policy.yaml"


def test_redirect_policy_rules():
    config = load_policy(policy_path)
    guard = PolicyGuard(config, domain="test")

    cases = [
        ("cat /sys/class/infiniband/mlx5_200/hca_type 2>/dev/null", Decision.ALLOW),
        ("cat /proc/cpuinfo 2>/dev/null", Decision.ALLOW),
        ("dmesg 2>/dev/null | tail", Decision.ALLOW),
        ("smartctl -a /dev/sda 2>/dev/null", Decision.ALLOW),
        ("cat foo > /dev/null", Decision.ALLOW),
        ("ls 2>/dev/null", Decision.ALLOW),
        ("command -v mpstat 2>/dev/null", Decision.ALLOW),
        ("echo test > /tmp/hack", Decision.DENY),
        ("ls > /tmp/out.txt", Decision.DENY),
        ("echo x >> /etc/passwd", Decision.DENY),
        ("cat /etc/shadow > /tmp/stolen", Decision.DENY),
    ]

    for command, expected in cases:
        assert guard.check_command(command) == expected, command
