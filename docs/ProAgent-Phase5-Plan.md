# ProAgent Phase 5 计划：Develop Agent + 四 Agent 产品化闭环

> 版本: v0.5 Draft
> 日期: 2026-05-20
> 前置: Phase 4 已完成 SRE / AIGC / Test 三 Agent 闭环与 Streamlit GUI
> 目标: 新增 Develop Agent，完成 Discord 7x24 入口、Web UI 历史/状态、自动 Skill、Memory、Token usage、Hermes 裁剪的产品化计划。

---

## 1. Phase 5 范围

### 1.1 Agent 关系

| Agent | 角色 | 关系 |
| --- | --- | --- |
| SRE Agent | Lab SRE，负责 Storage / GPU server / K8S 巡检、状态检查、故障排查 | 被 Test Agent 验证；缺陷和新需求交给 Develop Agent |
| Test Agent | Requirement driven 测试 Agent，运行真实测试、单元测试、回归测试 | 验证 SRE/AIGC/Develop Agent 是否满足 PRD |
| AIGC Agent | 娱乐与创作 Agent | 独立于主产品闭环，通过 Discord 使用 |
| Develop Agent | Feature / bugfix driven 开发 Agent | 开发 SRE Agent 能力，修复缺陷，更新 PRD/phase docs，交给 Test Agent 验证 |

命名统一为 **Develop Agent**。

### 1.2 In Scope

- 新增 Develop Agent Domain Pack。
- Discord slash agent router：`/aigc`、`/test`、`/develop`、`/sre`。
- Discord gateway 7x24 hardening 和 Docker 部署。
- Web UI 展示 SRE/Test/Develop 的 session history、Develop work items、test case/status。
- AIGC 保持 Discord-only，不进入主 Web UI。
- Hermes 保留/裁剪清单落地为 archive plan。
- 自动创建 skill 的 draft/review/enable 流程。
- Memory 分层与 token usage 持久化。
- 文档 hook：feature 级代码变更、新设计、进入下一 phase 必须更新 redesign plan + phase doc + 必要时 AGENTS.md。

### 1.3 Out of Scope

- SRE 自动执行生产写操作。
- 多租户企业级 RBAC 的完整实现。
- K8S controller/operator 形态部署。
- AIGC Web gallery 重构。

---

## 2. 目标架构

```
Discord / Web UI / CLI
        │
        ▼
Agent Router
  ├── /sre      → SRE Agent      → Lab status / troubleshooting / reports
  ├── /test     → Test Agent     → requirement tests / unit tests / reports
  ├── /develop  → Develop Agent  → feature / bugfix / docs / code
  └── /aigc     → AIGC Agent     → fun generation only
        │
        ▼
Shared Runtime Services
  ├── Session History
  ├── Work Item Store
  ├── Skill Draft Store
  ├── Layered Memory
  ├── Usage Tracker
  └── Policy Guard / Audit
```

Storage starts with SQLite:

| Store | File | Purpose |
| --- | --- | --- |
| Session History | `proagent/storage/session_history.db` | agent sessions, messages, summaries, tool events |
| Work Items | `proagent/storage/work_items.db` | PRD/feature/bugfix/test status |
| Usage | `proagent/storage/usage.db` | token usage and estimated cost |
| Skill Drafts | `proagent/storage/skill_drafts.db` | generated skill drafts, review status, evidence |

---

## 3. Develop Agent Requirements

### 3.1 Domain Pack

Create:

```
proagent/domain/develop_agent/
├── pack.yaml
├── policy.yaml
├── system_prompt.md
├── knowledge/
│   └── index.md
├── skills/
│   ├── requirement_to_plan.md
│   ├── feature_implementation.md
│   ├── bugfix_workflow.md
│   └── docs_sync.md
└── tools/
    ├── code_read.py
    ├── code_edit.py
    ├── test_delegate.py
    └── docs_update.py
```

### 3.2 Behavior

- Must start from a work item: requirement, PRD, bug report, phase milestone, or explicit user request.
- Must update `docs/ProAgent-Redesign-Plan.md` or the current phase doc before feature-level code changes.
- Must update `AGENTS.md` when coding workflow, testing workflow, safety rules, or directory responsibilities change.
- Must hand off to Test Agent after implementation with changed files, test plan, and expected behavior.
- Must not modify AIGC/SRE/Test domains unless the work item explicitly scopes those files.

### 3.3 Policy

Allowed:
- Read project files.
- Edit ProAgent source/docs for scoped work items.
- Run project tests.
- Create reports and implementation summaries.

Denied unless explicitly approved:
- Secret or credential changes.
- Destructive git commands.
- Production SRE write actions.
- Moving large Hermes directories to archive without import/test validation.

---

## 4. Discord 7x24 Requirements

Slash commands:

| Command | Behavior |
| --- | --- |
| `/sre <request>` | Route request to SRE Agent |
| `/test <request>` | Route request to Test Agent |
| `/develop <request>` | Route request to Develop Agent |
| `/aigc <prompt>` | Route request to AIGC Agent |
| `/agent switch <name>` | Set channel/thread default agent |
| `/agent status` | Show gateway health and active sessions |
| `/agent usage [today|session]` | Show token usage |

Runtime requirements:
- Reconnect on Discord websocket disconnect.
- Heartbeat and healthcheck endpoint for Docker.
- Per channel/thread session isolation.
- Structured logs with session_id, agent_id, user_id, command.
- Persistent volumes for `proagent/storage/`, logs, generated reports, AIGC output.

Deployment files:
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- healthcheck command
- startup docs

---

## 5. Web UI Requirements

Web UI covers SRE/Test/Develop only.

| View | Required Data |
| --- | --- |
| Session History | agent, target, status, start/end time, summary, messages, tool events |
| SRE Operations | latest checks, troubleshooting sessions, reports, target status |
| Develop Board | work item, requirement link, phase doc link, changed files, implementation status, linked tests |
| Test Dashboard | test cases, latest run, pass/fail status, failure evidence, requirement coverage |
| Token Usage | agent/session/provider/model tokens, estimated cost, daily total |

Acceptance:
- A user can open one SRE troubleshooting session and see what commands/tools were used.
- A user can see what Develop Agent is currently building and whether Test Agent validated it.
- A user can see failed tests with enough evidence to reproduce.

---

## 6. Hermes Keep / Archive Plan

Keep or adapt:
- `agent/usage_pricing.py`
- transport usage extraction in `agent/transports/`
- `agent/memory_manager.py`, `agent/memory_provider.py`
- `agent/skill_*`, `tools/skills_*`, `tools/skill_usage.py`, `tools/skill_manager_tool.py`
- `hermes_state.py` session search concepts
- `gateway/platforms/discord.py`, gateway session/status/restart support
- `tools/registry.py`, path safety, approval, tool guardrails

Archive or disable from ProAgent default path:
- Non-target chat platforms.
- Upstream website/docs site.
- RL/training/benchmark code.
- Entertainment/media tools outside AIGC.
- Unused model adapters outside configured provider list.

Archive rule:
- Before moving code, run import checks for ProAgent CLI, domain loading, policy guard, Discord gateway, GUI helpers.
- Keep moved code under `archive/hermes/<area>/` with a short `README.md` explaining why it was archived and how to restore.

---

## 7. Skill Automation Requirements

Flow:

```
Repeated workflow or user says "save this as a skill"
        │
        ▼
Skill draft with evidence + allowed tools + stop conditions
        │
        ▼
Test Agent dry-run test generation
        │
        ▼
User/reviewer approve
        │
        ▼
Enable skill and record version
```

Skill draft must include:
- name, description, owner agent
- when to use
- inputs required
- allowed tools
- procedure
- stop conditions
- output format
- tests
- source session/evidence

---

## 8. Memory Requirements

Layers:

| Layer | Examples |
| --- | --- |
| User | language preference, report format preference |
| Lab | topology, naming, maintenance window, common failure modes |
| Target | server hardware, baseline metrics, incident history |
| Agent | current work status, known limitations, recent validated workflows |

Rules:
- Do not store secrets.
- Inject summaries and retrieval snippets, not full raw history.
- Keep memory cache-aware; avoid mutating system context mid-session.
- Support Web UI inspection of memory items by layer.
- User-layer memory is isolated by gateway/user identity. A memory written for one Discord/Web/CLI user must not be injected into another user's agent context.
- Agents may persist explicit customer preferences and recurring requirements through user-scoped memory tools; these records are retrieved on later turns for the same user only.

---

## 9. Token Usage Requirements

Hermes already has token usage logic in `agent/usage_pricing.py` and transport usage extraction. ProAgent must persist this for all Agent calls.

Fields:

```
UsageRecord:
  session_id
  agent_id
  provider
  model
  input_tokens
  output_tokens
  cache_read_tokens
  cache_write_tokens
  reasoning_tokens
  estimated_cost
  created_at
```

UI/Discord:
- Web UI token usage page.
- `/agent usage today`
- `/agent usage session`
- Budget alert when daily threshold is exceeded.

---

## 10. Milestones

| # | Milestone | Deliverable | Status |
| --- | --- | --- | --- |
| M5.1 | Develop Agent Pack | domain pack, prompt, policy, skills | Completed baseline |
| M5.2 | Work Item Store | PRD/feature/bugfix/test status schema | Completed baseline |
| M5.3 | Discord Router | slash commands and channel default agent | Completed baseline |
| M5.4 | Gateway Hardening | reconnect, heartbeat, healthcheck, Docker | Completed baseline |
| M5.5 | Session History | persistent sessions and Web UI history | Completed baseline |
| M5.6 | Develop Board | feature/bugfix status view | Completed baseline |
| M5.7 | Test Dashboard | test case and requirement status view | Completed baseline |
| M5.8 | Skill Drafts | auto draft, approval, dry-run validation | Completed baseline |
| M5.9 | Memory Upgrade | layered memory and retrieval summaries | Completed baseline |
| M5.10 | Usage Tracking | usage.db, Web UI, Discord command | Completed baseline |
| M5.11 | Hermes Archive | archive pass with validation | Completed baseline |
| M5.12 | E2E | Test Agent validates four-agent flows | Completed baseline |

### 10.1 Progress Record (2026-05-20)

Delivered deployable Phase 5 baseline:

- `proagent/domain/develop_agent/` with pack metadata, prompt, policy, knowledge, and workflow skills.
- `proagent/storage/phase5.py` with `SessionHistoryStore`, `WorkItemStore`, and `UsageStore`.
- `proagent/core/agent_router.py` with `/sre`, `/test`, `/develop`, `/aigc`, `/agent switch`, `/agent status`, and `/agent usage`.
- `proagent gateway` writes session history and exposes `/health` for Docker healthchecks.
- Web UI adds Session History, Develop Board, Test Dashboard, and Token Usage panels.
- ProAgent deployment files: `Dockerfile.proagent`, `docker-compose.proagent.yml`, `.env.proagent.example`.

Focused verification:

```bash
python -m pytest proagent/tests/test_phase5_productization.py proagent/domain/test_agent/tests/test_gui.py -q --override-ini addopts=
```

### 10.2 Completion Record (2026-05-20)

Completed the remaining Phase 5 baseline:

- `UsageStore` is connected to `ProAgent` provider responses and records token usage when providers return usage metadata.
- `SkillDraftStore` supports draft creation, status transitions, and enabling a draft into a domain pack `skills/` directory.
- `LayeredMemoryStore` supports user/lab/target/agent memory upsert, listing, and search.
- Web UI adds Memory and Skill Drafts inspection panels.
- User-scoped memory is now part of the agent loop baseline: `ProAgent` can inject relevant memory for the current `user_id`, and built-in `memory_remember` / `memory_search` tools write and read only that user's memory.
- Develop Agent tools now include `work_item_create`, `work_item_update`, `code_read`, `code_edit`, `docs_update`, and `test_delegate`.
- `docs/Hermes-Archive-Plan.md` defines keep/archive candidates and validation gates.

Focused verification:

```bash
python -m pytest proagent/tests/test_phase5_productization.py -q --override-ini addopts=
```

---

## 11. DoD

1. `/sre`, `/test`, `/develop`, `/aigc` route to isolated sessions in Discord.
2. Discord gateway runs in Docker with healthcheck and persistent storage.
3. Develop Agent can create/update a work item, update docs, implement scoped code, and hand off to Test Agent.
4. Test Agent records pass/fail status and evidence for Develop Agent changes.
5. Web UI shows SRE history, Develop work items, Test status, and token usage.
6. AIGC remains isolated and Discord-only.
7. At least one skill goes through draft → review → enable → dry-run validation.
8. Token usage is captured for every LLM call.
9. Hermes archive pass does not break ProAgent CLI, domain load, policy guard, Discord gateway import, or GUI import.

---

## 12. Documentation Hook

Every feature-level code change must update docs first:

1. Update `docs/ProAgent-Redesign-Plan.md` for product/architecture decisions.
2. Update this phase doc for milestone status, detailed requirements, and design changes.
3. Update `AGENTS.md` when coding instructions, testing workflow, safety rules, or project structure change.

This hook is part of the requirement process, not optional cleanup.
