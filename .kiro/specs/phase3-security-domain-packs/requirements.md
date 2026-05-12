# Phase 3 Requirements: Security + Domain Packs + Execution Backends

## Introduction

Phase 3 transforms ProAgent from a working prototype into a production-grade professional agent runtime. Four workstreams run in parallel:
1. Security hardening (audit, guardrails, rollback interface)
2. Domain Pack system (SRE rename + new AIGC pack)
3. Execution backend design for production
4. Continuous Hermes code cleanup

## Glossary

- **LLM Audit**: Recording every LLM API call (model, tokens, latency, cost)
- **Operation Audit**: Recording every tool execution (command, target, result, decision)
- **Safety Guardrail**: Code-level enforcement that blocks forbidden content before it reaches execution
- **Domain Pack**: Self-contained plugin that gives the Agent a specific professional identity
- **Execution Backend**: The mechanism by which commands are delivered to target systems (SSH, local, Docker, K8s exec)

---

## Requirement 1: LLM Call Audit

**User Story:** As a platform operator, I want every LLM API call logged with model/tokens/latency/cost, so that I can track usage and debug issues.

### Acceptance Criteria

1. Every call to OpenAI/Anthropic/MiniMax API is recorded in `audit.db` table `llm_call`
2. Fields: timestamp, session_id, provider, model, prompt_tokens, completion_tokens, latency_ms, estimated_cost, status (ok/error)
3. `python proagent_run.py audit llm --last 20` shows recent LLM calls
4. Cost estimation uses per-model pricing table (configurable)

---

## Requirement 2: Safety Guardrails

**User Story:** As a security engineer, I want the agent to refuse processing prompts containing forbidden content, so that the system cannot be weaponized.

### Acceptance Criteria

1. A configurable `guardrails.yaml` defines:
   - `forbidden_words`: list of strings that trigger immediate rejection
   - `sensitive_patterns`: regex patterns for PII/credentials/injection attempts
   - `system_command_denylist`: additional command patterns beyond policy.yaml
2. Input guardrail: user messages are scanned BEFORE reaching the LLM
3. Output guardrail: LLM responses are scanned BEFORE being delivered to user
4. Blocked content returns a safe error message, not the forbidden content
5. All guardrail triggers are logged in audit_event with decision="guardrail_blocked"

---

## Requirement 3: Rollback Interface (Reserved)

**User Story:** As a developer, I want a rollback interface defined now (even though write ops are disabled), so that Phase 4 write operations can be safely reverted.

### Acceptance Criteria

1. `proagent/policy/rollback.py` defines the `RollbackCapable` protocol:
   - `checkpoint()` → saves current state before a write operation
   - `rollback(checkpoint_id)` → reverts to saved state
   - `list_checkpoints()` → shows available rollback points
2. The interface is importable and documented but raises `NotImplementedError` in Phase 3
3. `write_action` tools in future packs must implement this protocol
4. Design doc explains how rollback will work for: file changes, service restarts, k8s operations

---

## Requirement 4: AIGC Domain Pack

**User Story:** As a content creator, I want to switch the agent to AIGC mode and generate images/audio using MiniMax CLI, so that I can produce creative content through natural language.

### Acceptance Criteria

1. New domain pack at `proagent/domain/aigc_creator/`
2. Pack includes: pack.yaml, system_prompt.md, skills (image_gen, audio_gen), policy.yaml
3. MiniMax CLI installed and wrapped as a tool (`aigc_generate`)
4. `python proagent_run.py domain use aigc-creator` switches the active domain
5. In AIGC mode, user can say "生成一张熊猫动漫风格图片" and get an image
6. AIGC pack has its own policy.yaml (allows MiniMax CLI, denies SSH/system commands)
7. Domain switch is clean: SRE tools not available in AIGC mode, and vice versa

---

## Requirement 5: Domain Switch CLI

**User Story:** As an operator, I want to switch between SRE and AIGC domains via CLI, so that the same runtime serves different professional roles.

### Acceptance Criteria

1. `python proagent_run.py domain list` shows available packs
2. `python proagent_run.py domain use <pack-id>` switches active domain
3. Switch updates `proagent.yaml` runtime.domain field
4. After switch, `python proagent_run.py run` uses the new domain's prompt/tools/policy
5. Switching is instant (no restart required for CLI; gateway needs restart)

---

## Requirement 6: Execution Backend Abstraction

**User Story:** As an architect, I want execution backends abstracted behind a clean interface, so that new backends (Docker exec, K8s exec, local) can be added without changing agent code.

### Acceptance Criteria

1. `proagent/core/backends.py` defines `ExecutionBackend` protocol:
   - `connect(target) → bool`
   - `execute(command, timeout) → (rc, output)`
   - `health_check() → status`
   - `disconnect()`
2. Current SSH pool refactored to implement this protocol
3. `local` backend implements the same protocol (subprocess)
4. Config supports per-target backend selection (already in proagent.yaml)
5. Future backends (docker exec, k8s exec) can be added by implementing the protocol

---

## Requirement 7: Hermes Code Cleanup (Ongoing)

**User Story:** As a maintainer, I want unused Hermes code progressively removed, so that the codebase stays lean and focused on ProAgent's professional domain.

### Acceptance Criteria

1. A tracking file `docs/cleanup-tracker.md` lists:
   - Modules already removed (Phase 1: 66 files, 57k LOC)
   - Modules identified for removal (with dependency analysis)
   - Modules to keep (with justification)
2. Each cleanup commit references the tracker
3. `python proagent/tests/test_basic.py` must pass after every cleanup
4. No cleanup breaks the `proagent_run.py` entry point

---

## Correctness Properties

1. **Audit completeness**: Every LLM call and every tool execution MUST have a corresponding audit record. No silent operations.
2. **Guardrail ordering**: Input guardrails fire BEFORE LLM call. Output guardrails fire BEFORE delivery. Never the reverse.
3. **Domain isolation**: When domain=aigc, SRE tools are not callable. When domain=sre, AIGC tools are not callable. Cross-domain tool access is impossible.
4. **Backend abstraction**: Changing a target's backend type does not require changes to agent.py or any domain pack code.
5. **Rollback safety**: The rollback interface cannot be called in Phase 3 (raises NotImplementedError). It exists only as a contract.
