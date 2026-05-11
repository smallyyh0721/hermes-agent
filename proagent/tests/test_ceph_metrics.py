"""Quick test: fetch Ceph metrics from the real server."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from proagent.core.config import load_config
from proagent.core.runtime import ProAgentRuntime

config = load_config()
runtime = ProAgentRuntime(config=config)
results = runtime.connect_targets()

target = config.default_target
if not results.get(target):
    print(f"Cannot connect to {target}")
    sys.exit(1)

print(f"Connected to {target}")
print()

# Test 1: Ceph health
print("=== Ceph Health ===")
rc, out = runtime.execute_on_target(
    'curl -s --connect-timeout 5 http://10.11.4.20:9283/metrics | grep -E "^ceph_health_status" | head -5',
    target_id=target
)
print(f"rc={rc}")
print(out[:300] if out else "(empty)")
print()

# Test 2: Ceph OSD
print("=== Ceph OSD ===")
rc, out = runtime.execute_on_target(
    'curl -s --connect-timeout 5 http://10.11.4.20:9283/metrics | grep -E "^ceph_osd_up " | head -10',
    target_id=target
)
print(f"rc={rc}")
print(out[:500] if out else "(empty)")
print()

# Test 3: Node exporter
print("=== Node Exporter ===")
rc, out = runtime.execute_on_target(
    'curl -s --connect-timeout 5 http://10.11.4.20:9100/metrics | grep -E "^node_filesystem_avail_bytes" | head -5',
    target_id=target
)
print(f"rc={rc}")
print(out[:500] if out else "(empty)")
print()

# Test 4: JuiceFS (may not be on this node)
print("=== JuiceFS ===")
rc, out = runtime.execute_on_target(
    'curl -s --connect-timeout 5 http://localhost:9567/metrics 2>/dev/null | grep -E "^juicefs_" | head -5',
    target_id=target
)
print(f"rc={rc}")
print(out[:300] if out else "(empty or not available on this node)")

runtime.ssh_pool.disconnect_all()
print()
print("Done.")
