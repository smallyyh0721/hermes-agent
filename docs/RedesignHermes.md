# Hermes 改造成专业 Agent 的核心方案

## 核心思路

将 Hermes 从“泛用个人 Agent”裁剪为“专业领域 Agent Runtime”。

目标不是做一个什么都能聊天的 AI 助手，而是构建：

- 领域知识驱动
- 长期记忆
- SOP/Skill 沉淀
- 强权限控制
- 可审计
- 可复盘
- 可扩展工具链

的专业 Agent 系统。

---

# 一、总体架构

```
Domain Event / API / CLI
        ↓
Task Router
        ↓
Hermes Core Agent
  - agent loop
  - prompt builder
  - memory retrieval
  - skill retrieval
  - tool dispatch
        ↓
Domain Tool Layer
  - SRE tools
  - Testing tools
  - Finance tools
        ↓
Policy Guard
  - permission
  - approval
  - audit
  - sandbox
        ↓
Result / Report / Ticket / PR
```

---

# 二、保留 Hermes 的核心能力

## 必须保留

| 模块 | 原因 |
| --- | --- |
| Agent Loop | Runtime 核心 |
| Prompt Builder | 注入领域规则、memory、skills |
| Session Storage | 历史任务、审计、复盘 |
| Memory | 长期知识与经验 |
| Skills | SOP/经验沉淀 |
| Tool Dispatch | 专业工具调用 |
| Context Files | [AGENTS.md](http://AGENTS.md) / [MEMORY.md](http://MEMORY.md) 等项目规则 |

---

# 三、删除/裁剪部分

## 删除多聊天入口

不再需要：

- Telegram
- WhatsApp
- Signal
- QQ
- 泛用聊天 Gateway

保留：

- REST API
- WeChat
- Discord
- CLI
- Webhook
- Scheduler/Cron
- Internal Event Bus

---

# 四、模型层精简

不要做“模型市场”。

推荐只保留：

但是需要具备openai/anthropic接口适配，预留其他模型市场能力

```yaml
models:
  planner:
    provider: minimax
    model: m2.7

  executor:
    provider: minimax
    model: m2.5

  summarizer:
    provider: minimax
    model: m2.5

  verifier:
    provider: minimax
    model: m2.7
```

原则：

- 稳定 > 多样
- 可追踪 > 炫技
- Function calling 稳定性优先

---

# 五、Tool 架构改造

## 三层 Tool 分类

```
tools/
  read_only/
  suggest/
  write_action/
```

---

## SRE Agent 示例

### read_only

- prometheus_query
- grafana_read
- kubernetes_get
- logs_search
- trace_search

### suggest

- incident_summary
- root_cause_hypothesis
- rollback_plan_generate

### write_action

- kubernetes_restart
- rollback_release
- scale_deployment

生产写操作必须审批。

---

## Testing Agent 示例

### read_only

- repo_read
- ci_log_read
- coverage_read

### suggest

- test_case_generate
- flaky_test_diagnose

### write_action

- create_test_file
- rerun_ci
- open_pr

---

## Finance Agent 示例

### read_only

- sec_filing_fetch
- market_data_read
- spreadsheet_read

### suggest

- valuation_model_generate
- peer_compare

### write_action

- generate_report
- update_dashboard

不允许直接交易。

---

# 六、Skill 系统改造

不要无限自动生成泛用 Skill。但是可以根据任务生成新的skill和tool，有些常规任务类似Skill SOP。

目录结构：

```
skills/
  sre/
  testing/
  finance/
```

每个 Skill 模板：

```markdown
# Skill Name

## When to use

## Inputs required

## Procedure

## Tools allowed

## Stop conditions

## Output format

## Examples
```

---

# 七、Memory 改造

从“个人长期记忆”改成“领域知识库”。

```
memory/
  domain_knowledge.md
  system_inventory.md
  runbook_index.md
  incident_history.md
  decision_log.md
  user_preferences.md
```

建议采用：

- index + 子文档
- retrieval on demand
- 避免单个 [MEMORY.md](http://MEMORY.md) 无限膨胀

---

# 八、最关键：Policy Guard

专业 Agent 必须有硬权限边界。

不能只靠 Prompt。

```yaml
permissions:
  read_only:
    auto_execute: true

  suggest:
    auto_execute: true

  write_action:
    require_approval: true

  destructive:
    forbidden: true
```

SRE 示例：

```yaml
forbidden:
  - delete_namespace
  - drop_database
  - rotate_secrets_without_ticket
```

---

# 九、推荐目录结构

```
professional-agent/
  agent/
    core_loop.py
    prompt_builder.py
    tool_dispatcher.py
    memory_manager.py
    skill_manager.py

  domain/
    sre/
    testing/
    finance/

  gateway/
    api.py
    cli.py
    webhook.py

  security/
    permission.py
    approval.py
    audit_log.py
    sandbox.py

  storage/
    sessions.db
    audit.db
```

---

# 十、推荐演进路线

## V1

- API/CLI
- Agent Loop
- Memory
- 5 个核心 Tools
- Audit

## V2

- 权限分级
- 审批流
- 任务状态机

## V3

- 自动 Skill 生成
- Human Review

## V4

- Multi-Agent
    - Planner
    - Executor
    - Verifier
    - Reporter

---

# 最终结论

专业 Agent 的核心不是“聊天能力”，而是：

- 领域知识
- 工具编排
- SOP 沉淀
- 长期记忆
- 权限治理
- 可审计执行

Hermes 最有价值的部分：

- Agent Loop
- Memory
- Skills
- Tool Dispatch
- Session/Audit

最应该删除的部分：

- 多聊天平台
- 过多模型适配
- 泛用娱乐工具
- 无约束自动学习
- 无权限边界执行

最终目标：

把 Hermes 从“个人 AI 助手”改造成“专业领域 Agent Runtime”。