"""Test kubectl policy rules - read allowed, write denied."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from proagent.policy.guard import PolicyGuard, load_policy, Decision

policy_path = Path(__file__).resolve().parents[1] / "domain" / "server_health_inspector" / "policy.yaml"
config = load_policy(policy_path)
guard = PolicyGuard(config, domain="test")

tests = [
    # Should ALLOW (read-only kubectl)
    ("kubectl get pods -A", Decision.ALLOW),
    ("kubectl describe node server-01", Decision.ALLOW),
    ("kubectl logs pod-123 -f", Decision.ALLOW),
    ("kubectl top nodes", Decision.ALLOW),
    ("kubectl get svc -n monitoring", Decision.ALLOW),
    ("kubectl cluster-info", Decision.ALLOW),
    # Should DENY (write kubectl)
    ("kubectl delete pod x", Decision.DENY),
    ("kubectl apply -f x.yaml", Decision.DENY),
    ("kubectl scale deploy x --replicas=0", Decision.DENY),
    ("kubectl edit deploy x", Decision.DENY),
    ("kubectl create ns test", Decision.DENY),
    ("kubectl drain node-01", Decision.DENY),
    ("kubectl cordon node-01", Decision.DENY),
    # Should DENY (helm write)
    ("helm install x y", Decision.DENY),
    ("helm upgrade x y", Decision.DENY),
    ("helm uninstall x", Decision.DENY),
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
    print("All kubectl policy tests passed!")
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)
