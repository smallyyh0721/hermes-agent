"""Integration test: fetch Ceph metrics from the real lab server."""
import os
from pathlib import Path

import pytest

from proagent.core.config import load_config
from proagent.core.runtime import ProAgentRuntime


pytestmark = pytest.mark.skipif(
    os.environ.get("PROAGENT_RUN_LAB_INTEGRATION") != "1",
    reason="requires real lab SSH/network access; set PROAGENT_RUN_LAB_INTEGRATION=1 to run",
)


def test_ceph_metrics_from_real_server():
    config = load_config()
    runtime = ProAgentRuntime(config=config)
    try:
        results = runtime.connect_targets()
        target = config.default_target
        if not results.get(target):
            pytest.skip(f"cannot connect to {target}")

        checks = [
            'curl -s --connect-timeout 5 http://10.11.4.20:9283/metrics | grep -E "^ceph_health_status" | head -5',
            'curl -s --connect-timeout 5 http://10.11.4.20:9283/metrics | grep -E "^ceph_osd_up " | head -10',
            'curl -s --connect-timeout 5 http://10.11.4.20:9100/metrics | grep -E "^node_filesystem_avail_bytes" | head -5',
            'curl -s --connect-timeout 5 http://localhost:9567/metrics 2>/dev/null | grep -E "^juicefs_" | head -5',
        ]
        for command in checks:
            rc, out = runtime.execute_on_target(command, target_id=target)
            assert rc in (0, 1), command
            assert out is not None
    finally:
        runtime.ssh_pool.disconnect_all()
