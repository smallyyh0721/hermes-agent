"""Test kubectl policy rules - read allowed, write denied."""
from pathlib import Path

from proagent.policy.guard import PolicyGuard, load_policy, Decision

policy_path = Path(__file__).resolve().parents[1] / "domain" / "server_health_inspector" / "policy.yaml"


def test_kubectl_policy_rules():
    config = load_policy(policy_path)
    guard = PolicyGuard(config, domain="test")

    cases = [
        ("kubectl get pods -A", Decision.ALLOW),
        ("kubectl describe node server-01", Decision.ALLOW),
        ("kubectl logs pod-123 -f", Decision.ALLOW),
        ("kubectl top nodes", Decision.ALLOW),
        ("kubectl get svc -n monitoring", Decision.ALLOW),
        ("kubectl cluster-info", Decision.ALLOW),
        ("kubectl delete pod x", Decision.DENY),
        ("kubectl apply -f x.yaml", Decision.DENY),
        ("kubectl scale deploy x --replicas=0", Decision.DENY),
        ("kubectl edit deploy x", Decision.DENY),
        ("kubectl create ns test", Decision.DENY),
        ("kubectl drain node-01", Decision.DENY),
        ("kubectl cordon node-01", Decision.DENY),
        ("helm install x y", Decision.DENY),
        ("helm upgrade x y", Decision.DENY),
        ("helm uninstall x", Decision.DENY),
    ]

    for command, expected in cases:
        assert guard.check_command(command) == expected, command
