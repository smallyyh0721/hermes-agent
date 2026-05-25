# Hermes Archive Plan

> Date: 2026-05-20
> Scope: Phase 5 archive pass for ProAgent productization.

This document records the archive strategy for Hermes code that is not on the
default ProAgent runtime path. Phase 5 keeps the code in place until import and
runtime validation are clean because broad file moves can silently break package
imports.

## Keep

- Agent loop and provider transport concepts.
- Usage extraction and pricing references in `agent/usage_pricing.py`.
- Memory and skill lifecycle concepts.
- Discord gateway implementation references.
- Tool registry, policy guard, path safety, and approval concepts.

## Archive Candidates

- Non-target messaging platforms outside Discord and future Feishu.
- Upstream website/docs site that is unrelated to ProAgent operations.
- RL, training, benchmark, and dataset generation code.
- Entertainment/media tools outside the AIGC domain pack.
- Unused model adapters outside the configured provider list.

## Archive Rule

Move code only into `archive/hermes/<area>/` with a README explaining why it was
archived and how to restore it. Do not delete code during Phase 5.

## Validation commands

Run these before and after each archive move:

```bash
python -m pytest proagent/tests/test_basic.py proagent/tests/test_redirect.py proagent/tests/test_kubectl_policy.py proagent/tests/test_phase5_productization.py proagent/domain/test_agent/tests/test_gui.py -q --override-ini addopts=
python proagent_run.py domain list
python -m py_compile proagent/cli/main.py proagent/core/agent.py proagent/core/agent_router.py proagent/storage/phase5.py proagent/gui/app.py
```

The Phase 5 baseline does not physically move large Hermes directories yet. It
ships the archive plan and validation gate so subsequent archive work can happen
incrementally without breaking ProAgent CLI, domain loading, policy guard,
Discord gateway imports, or GUI imports.
