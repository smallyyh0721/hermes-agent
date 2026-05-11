"""Test redirect pattern fix - allow 2>/dev/null, block writes to real files."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from proagent.policy.guard import PolicyGuard, load_policy, Decision

policy_path = Path(__file__).resolve().parents[1] / "domain" / "server_health_inspector" / "policy.yaml"
config = load_policy(policy_path)
guard = PolicyGuard(config, domain="test")

tests = [
    # Should ALLOW (redirect to /dev/null is safe)
    ("cat /sys/class/infiniband/mlx5_200/hca_type 2>/dev/null", Decision.ALLOW),
    ("cat /proc/cpuinfo 2>/dev/null", Decision.ALLOW),
    ("dmesg 2>/dev/null | tail", Decision.ALLOW),
    ("smartctl -a /dev/sda 2>/dev/null", Decision.ALLOW),
    ("cat foo > /dev/null", Decision.ALLOW),
    ("ls 2>/dev/null", Decision.ALLOW),
    ("command -v mpstat 2>/dev/null", Decision.ALLOW),
    # Should DENY (redirect to real files)
    ("echo test > /tmp/hack", Decision.DENY),
    ("ls > /tmp/out.txt", Decision.DENY),
    ("echo x >> /etc/passwd", Decision.DENY),
    ("cat /etc/shadow > /tmp/stolen", Decision.DENY),
]

all_pass = True
for cmd, expected in tests:
    result = guard.check_command(cmd)
    status = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_pass = False
    print(f"  {status}: {cmd}")
    if result != expected:
        print(f"        got {result}, expected {expected}")

print()
if all_pass:
    print("All redirect pattern tests passed!")
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)
