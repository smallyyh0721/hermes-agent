# Hermes → ProAgent 改造方案与产品 SPEC

> 本文档是 `docs/RedesignHermes.md` 初步思路的细化版本，作为 Hermes 改造为"专业领域 Agent Runtime（ProAgent）"的正式设计文档与第一阶段产品规格（Product SPEC）。
>
> - 版本: v0.1 (Draft)
> - 基线仓库: `hermes-agent` (upstream: NousResearch/hermes-agent)
> - 目标形态: **领域可插拔的专业 Agent Runtime**，可快速转型到 SRE、Testing、Finance、DBA 等任一专业领域
> - 第一阶段落地: **单机服务器健康巡检与状态分析 Agent**（只读、WeChat + Discord 入口）

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [设计原则](#2-设计原则)
3. [Hermes 能力盘点与裁剪矩阵](#3-hermes-能力盘点与裁剪矩阵)
4. [最终目标架构（ProAgent Runtime）](#4-最终目标架构proagent-runtime)
5. [领域包（Domain Pack）机制：快速转型的关键](#5-领域包domain-pack机制快速转型的关键)
6. [第一阶段范围：Server Health Inspector Agent](#6-第一阶段范围server-health-inspector-agent)
7. [产品 SPEC（Phase 1）](#7-产品-specphase-1)
8. [里程碑与演进路线](#8-里程碑与演进路线)
9. [验收标准（DoD）](#9-验收标准dod)
10. [风险与缓解](#10-风险与缓解)
11. [附录](#11-附录)
12. [Phase 4 计划：三 Agent 闭环 + 统一 GUI 入口](#12-phase-4-计划三-agent-闭环--统一-gui-入口)
13. [Phase 5 计划：四 Agent 产品化 + 7x24 Discord Gateway](#13-phase-5-计划四-agent-产品化--7x24-discord-gateway)

---

## 1. 背景与目标

### 1.1 现状

Hermes Agent 是一款"自我改进型通用个人助理"，具备：

- 强大的 Agent Loop（`agent/`）、Prompt Builder、Memory、Skills、Tool Dispatch
- 极广的对外入口（Telegram / Discord / Slack / WhatsApp / Signal / WeChat / Feishu / Email / Matrix / Mattermost / SMS / BlueBubbles / HomeAssistant / Yuanbao / DingTalk / ...）
- 极广的模型适配（OpenAI / Anthropic / Gemini / Bedrock / OpenRouter / LMStudio / MiniMax / Moonshot / 小米 MiMo / GLM / Copilot / Google Code Assist / ...）
- 大量泛用工具（浏览器、图像生成、语音、邮件、看板、计算机操控、MCP 等）

这让 Hermes 在**通用场景**下非常强，但在**专业领域**下：

- 权限边界模糊，不可审计
- SOP 无法强制收敛
- 输出质量随 LLM 漂移，无领域护栏
- 无法向企业/客户交付稳定可预期的专业能力

### 1.2 目标

把 Hermes 改造为 **ProAgent**：一个**领域可插拔、权限可治理、流程可审计**的专业 Agent Runtime，具备：

1. **核心 Runtime 稳定单一**：只保留 Agent Loop / Prompt / Memory / Skills / Tool Dispatch / Session Audit
2. **领域能力插件化**：以 Domain Pack 形式装配（SRE Pack、Testing Pack、Finance Pack、DBA Pack …）
3. **权限硬边界**：三层工具分类（read_only / suggest / write_action）+ Policy Guard
4. **入口收敛**：只保留 REST API / WeChat / Discord / Feishu / CLI / Webhook / Scheduler / Internal Event Bus
5. **快速转型**：切换 Domain Pack 即可让同一 Runtime 变成另一领域的专家
6. **第一阶段小而完整**：用一台服务器健康巡检 Agent 走通端到端链路，摸清 Agent 设计要点

---

## 2. 设计原则

| 原则 | 含义 |
| --- | --- |
| **稳定 > 多样** | 模型、入口、工具都做收敛，不追数量 |
| **可追踪 > 炫技** | 每次调用、每条决策都落审计 |
| **Prompt 不是边界** | 权限、幂等、副作用必须由代码层硬守 |
| **领域知识是一等公民** | Memory 从"个人记忆"转为"领域知识库" |
| **SOP 沉淀即资产** | Skill 作为可复用、可审阅、可测试的流程模板 |
| **只读优先、先观察后动作** | Phase 1 完全只读；写操作永远需要审批 |
| **单机可运行，云上可扩展** | 复用 Hermes 既有多后端（本地 / Docker / SSH / Modal / Daytona）能力 |

---

## 3. Hermes 能力盘点与裁剪矩阵

### 3.1 保留（Core Runtime）

这些是 Hermes 最有价值的资产，ProAgent Runtime 的基石：

| 模块 | Hermes 中位置 | 保留理由 |
| --- | --- | --- |
| Agent Loop | `agent/`（`curator.py`、`context_engine.py` 等） | Runtime 心脏 |
| Prompt Builder | `agent/prompt_builder.py` | 注入领域规则 / memory / skills |
| Memory Manager | `agent/memory_manager.py`、`agent/memory_provider.py` | 领域知识检索 |
| Skill System | `skills/`、`agent/skill_*`、`tools/skills_*` | SOP 载体 |
| Tool Dispatcher | `tools/registry.py`、`tools/managed_tool_gateway.py` | 三层工具分层的天然容器 |
| Session Storage | `hermes_state.py`、FTS5 session search | 审计、复盘 |
| Context Files | `AGENTS.md` / `MEMORY.md` | 工作规则注入 |
| Approval 基础设施 | `tools/approval.py`、`tools/slash_confirm.py` | 扩展为 Policy Guard 审批流 |
| File/Path 安全 | `tools/file_safety.py`、`tools/path_security.py` | 继续作为工具边界 |
| Cron/Scheduler | `cron/` | 定时巡检触发器 |
| Multi-backend Shell | `tools/environments/`（local / docker / ssh / modal / daytona / singularity / vercel） | 连接目标服务器的基础 |
| I18n | `agent/i18n.py`、`locales/` | 中文输出 |
| Feishu 工具 | `tools/feishu_doc_tool.py`、`tools/feishu_drive_tool.py` | 飞书文档/云盘读写，作为协作输出通道 |

### 3.2 裁剪（Phase 1 移除或禁用）

> 采取策略：**先禁用（config 关闭 + 默认不加载）**，Phase 2 再做代码物理删除，保持 Git 历史清晰。

| 类别 | 涉及目录/文件 | 处理 |
| --- | --- | --- |
| 多聊天入口 | `gateway/platforms/telegram.py`、`whatsapp.py`、`signal.py`、`slack.py`、`matrix.py`、`mattermost.py`、`sms.py`、`bluebubbles.py`、`homeassistant.py`、`yuanbao*.py`、`dingtalk.py`、`email.py`、`qqbot/`、`wecom_*.py` | **禁用**（保留 `discord.py` / `weixin.py` / `feishu.py` / `api_server.py` / `webhook.py`） |
| 泛用娱乐工具 | `tools/image_generation_tool.py`、`tools/tts_tool.py`、`tools/transcription_tools.py`、`tools/voice_mode.py`、`tools/neutts_*`、`tools/vision_tools.py` | **禁用** |
| 浏览器/计算机操控 | `tools/browser_*`、`tools/computer_use*`、`tools/browser_providers/`、`tools/computer_use/` | **禁用**（Phase 3 若需要再按领域开放） |
| Yuanbao/MSGraph 等三方工具 | `tools/yuanbao_tools.py`、`tools/microsoft_graph_*`、`tools/homeassistant_tool.py` | **禁用**（保留 `tools/feishu_*` 飞书文档/云盘工具，作为协作输出通道） |
| 过多模型适配 | `agent/bedrock_adapter.py`、`agent/gemini_*`、`agent/codex_responses_adapter.py`、`agent/copilot_acp_client.py`、`agent/google_code_assist.py`、`agent/google_oauth.py`、`agent/moonshot_schema.py`、`agent/lmstudio_reasoning.py`、`agent/nous_rate_guard.py` | **按需保留**：Phase 1 仅启用 OpenAI 适配 + Anthropic 适配，其余降级为可选插件（`providers/`） |
| RL / Atropos / Tinker | `tinker-atropos/`、`rl_cli.py`、`tools/rl_training_tool.py`、`mini_swe_runner.py`、`batch_runner.py`、`trajectory_compressor.py` | **归档**（移入 `archived/`，Phase 1 不启用） |
| 无约束自动学习 | `agent/curator.py` 中的自动 skill 生成逻辑、`tools/skill_manager_tool.py` 写侧 | **降级为"建议生成，人工审核合并"**（Human-in-the-Loop） |
| Website / UI 非必要 | `website/`、`ui-tui/`、`web/` | **Phase 1 保留但不优先维护** |

### 3.3 新增（ProAgent 层）

| 新增模块 | 作用 |
| --- | --- |
| `proagent/core/` | Runtime 入口、领域装配、启动编排 |
| `proagent/domain/` | Domain Pack 基类 + 各领域实现 |
| `proagent/policy/` | Policy Guard（权限、审批、沙箱、审计） |
| `proagent/skills_pack/` | 按领域打包的 SOP Skills |
| `proagent/knowledge/` | 领域知识库（索引 + 子文档） |
| `proagent/tools_pack/` | 按领域打包的 Tools（read_only / suggest / write_action） |
| `proagent/planner/` | Multi-Agent（Planner / Executor / Verifier / Reporter）骨架（Phase 4 落地） |
| `proagent/gateway_profile/` | 入口裁剪配置（哪些 platform 启用） |

---

## 4. 最终目标架构（ProAgent Runtime）

### 4.1 分层图

```
┌─────────────────────────────────────────────────────────────┐
│  Inbound                                                    │
│   REST API | WeChat | Discord | Feishu | CLI | Webhook | Cron | Bus  │
└───────────────────────────┬─────────────────────────────────┘
                            │ Task Envelope
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Task Router  (tenant / domain / priority / scope)          │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ProAgent Core Runtime                                      │
│    Agent Loop → Prompt Builder → Memory → Skill → Tool     │
│              (复用 Hermes `agent/`)                         │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Domain Pack (hot-swappable)                                │
│    knowledge/  skills/  tools/  prompts/  policy.yaml       │
│    e.g. sre-inspector / testing / finance / dba ...         │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Policy Guard                                               │
│    permission | approval | sandbox | audit | quota          │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Execution Backends                                         │
│    local / ssh / docker / k8s-exec / modal / daytona …      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Outbound                                                   │
│    Chat Reply | Report | Ticket | PR | Dashboard | Metric   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 关键接口（概念 API）

```python
# proagent/core/runtime.py
class ProAgentRuntime:
    def __init__(self, domain: DomainPack, policy: PolicyGuard, gateways: list[Gateway]): ...
    async def handle(self, task: Task) -> TaskResult: ...

# proagent/domain/base.py
class DomainPack(Protocol):
    name: str
    system_prompt: str
    knowledge: KnowledgeStore
    skills: list[Skill]
    tools: ToolSet          # 三层分类
    policy: DomainPolicy    # 允许/禁止/需审批清单

# proagent/policy/guard.py
class PolicyGuard:
    def check(self, tool_call: ToolCall, actor: Actor) -> Decision: ...
    async def request_approval(self, tool_call: ToolCall) -> Approval: ...
    def audit(self, event: AuditEvent) -> None: ...
```

### 4.3 模型层策略

Phase 1 默认配置：

```yaml
models:
  planner:    { provider: openai,    model: gpt-4.1-mini }
  executor:   { provider: openai,    model: gpt-4.1-mini }
  summarizer: { provider: anthropic, model: claude-3-5-haiku }
  verifier:   { provider: anthropic, model: claude-3-5-sonnet }
adapters_enabled: [openai, anthropic]
adapters_optional: [minimax, moonshot, gemini, bedrock]   # 预留市场能力
```

原则：稳定 > 多样；Function Calling 稳定性优先；其余 adapter 以"可选插件"保留，不默认加载。

---

## 5. 领域包（Domain Pack）机制：快速转型的关键

### 5.1 Domain Pack 目录约定

```
proagent/domain/<domain_id>/
├── pack.yaml                 # 元数据：名称、版本、依赖、默认模型
├── system_prompt.md          # 领域系统提示词
├── knowledge/
│   ├── index.md              # 知识索引
│   ├── domain_overview.md
│   ├── runbook_index.md
│   ├── system_inventory.md
│   └── glossary.md
├── skills/
│   └── <skill_id>/
│       ├── SKILL.md          # When / Inputs / Procedure / Stop / Output
│       └── examples/
├── tools/
│   ├── read_only/
│   ├── suggest/
│   └── write_action/
├── policy.yaml               # 权限矩阵、禁止清单、审批规则
└── tests/                    # 领域能力回归用例
```

### 5.2 `pack.yaml` 示例（server-health-inspector）

```yaml
id: server-health-inspector
version: 0.1.0
display_name: 服务器健康巡检 Agent
description: 单机 Linux 服务器健康巡检与问题诊断（只读）
models:
  planner:    { provider: openai,    model: gpt-4.1-mini }
  executor:   { provider: openai,    model: gpt-4.1-mini }
  summarizer: { provider: anthropic, model: claude-3-5-haiku }
gateways:
  - weixin
  - discord
  - feishu
  - api
  - cron
capabilities:
  read_only: true
  suggest:   true
  write_action: false    # Phase 1 显式关闭
```

### 5.3 切换领域的用户体验

```bash
# 查看已安装的 Pack
proagent domain list

# 启用服务器健康巡检 Pack
proagent domain use server-health-inspector

# 切换到 SRE（未来）
proagent domain use sre-ops
```

Runtime 不变，Pack 换了 → Agent 就"转型"为另一领域专家。这是本项目最核心的架构价值。

### 5.4 Domain Pack 生命周期

```
install → validate(pack.yaml, policy) → load(knowledge, skills, tools)
       → register gateways → warm-up (knowledge index)
       → ready → use → deactivate → uninstall
```

---

## 6. 第一阶段范围：Server Health Inspector Agent

### 6.1 范围（In Scope）

- **目标对象**：单台 Linux 服务器（Ubuntu / CentOS / Rocky），本机运行或通过 SSH 接入
- **巡检维度**：
  - 硬件：CPU 负载 / 温度、内存、磁盘空间/IO、网络、SMART、PSU（可得时）
  - OS：uptime、kernel、systemd units、时间同步、文件句柄、inode、ulimit
  - 进程：top-N CPU/MEM、zombie、OOM 历史、关键服务状态（nginx/sshd/…）
  - 日志：`dmesg`、`journalctl` 错误摘要（近 24h）
- **触发方式**：
  1. **Cron 定时巡检**（默认每小时一次简检，每日一次深度巡检）
  2. **用户 IM 问答**（WeChat / Discord）："当前服务器状况如何？" / "根因是什么？"
  3. **Webhook 事件触发**（外部监控告警推过来 → Agent 进入诊断模式）
- **能力边界**：**完全只读**；任何 write_action 工具在 Phase 1 被 Policy Guard 硬拦截

### 6.2 不在范围（Out of Scope, Phase 1）

- 多台服务器拓扑巡检（Phase 2）
- 自动修复（重启、扩容、回滚）
- K8s 集群级视图
- 告警规则配置下发
- WeChat 群组管理

### 6.3 用户故事（User Stories）

| ID | Persona | Story | 验收要点 |
| --- | --- | --- | --- |
| US-1 | SRE / 运维 | 希望每天早上 9:00 在 Discord 收到服务器健康晨报 | Cron 触发 → 巡检 → Discord 推送 |
| US-2 | 运维 | 发现告警后在 WeChat 问 "web-01 现在怎么样？" → 立刻得到结构化诊断 | 自动拉取实时状态 + 近期日志摘要 |
| US-3 | 值班工程师 | 收到 "磁盘 85%" 告警后问 "根因？建议？" → Agent 给出 top-10 占用目录 + 建议清理路径（不执行） | suggest 层输出，无写操作 |
| US-4 | Team Lead | 希望看到 7 天健康趋势回顾 | session 历史 + memory 检索 |
| US-5 | 平台 Owner | 希望审计 Agent 的每一次工具调用 | 审计表可按 session 查询 |

### 6.4 领域技能（Skills, Phase 1 全部 read-only）

```
proagent/domain/server-health-inspector/skills/
├── quick_health_check/            # 5 分钟概览
├── full_health_inspection/        # 深度巡检（~60 项指标）
├── disk_pressure_diagnose/        # 磁盘压力根因
├── memory_pressure_diagnose/      # OOM / 内存泄漏诊断
├── cpu_hotspot_diagnose/          # CPU 热点
├── network_connectivity_check/    # 网络与端口
├── service_status_audit/          # systemd 单元状态
├── log_anomaly_scan/              # 日志异常扫描
└── incident_timeline_build/       # 事件时间线（供值班）
```

每个 Skill 遵循统一模板：

```markdown
# <Skill Name>
## When to use
## Inputs required
## Procedure (step-by-step, 工具调用计划)
## Tools allowed (白名单)
## Stop conditions
## Output format (结构化 JSON + 人类可读摘要)
## Examples
```

### 6.5 工具清单（Tools, Phase 1）

**read_only 层**（全部走 SSH / 本地 shell 包装，输出走 tool_output_limits 截断）：

> **设计原则**：read_only 工具不限制具体可执行的 shell 命令，Agent 可灵活使用任何系统命令进行诊断。安全边界由 Policy Guard 的 **denylist 模式**保证——匹配到写/破坏性模式的命令被硬拦截，其余默认放行。这确保了 Agent 面对未知问题时有足够的诊断灵活性。

以下为**常用命令参考**（非穷举，Agent 可根据诊断需要自由组合）：

| Tool | 命令/来源 | 输出 |
| --- | --- | --- |
| `host_meta` | `hostnamectl`, `uname -a`, `/etc/os-release` | JSON |
| `cpu_snapshot` | `mpstat 1 3`, `/proc/loadavg`, `lscpu` | JSON |
| `mem_snapshot` | `free -m`, `/proc/meminfo`, `vmstat 1 3` | JSON |
| `disk_snapshot` | `df -hT`, `iostat -x 1 3`, `du -x --max-depth=2 /`（限时） | JSON |
| `disk_smart` | `smartctl -a`（可得时） | JSON |
| `net_snapshot` | `ss -s`, `ss -tunap`, `ip -br a`, `ping`（白名单目标） | JSON |
| `proc_top` | `ps auxf --sort=-%cpu \| head -n 30` | JSON |
| `service_status` | `systemctl list-units --type=service --state=failed` 等 | JSON |
| `log_tail` | `journalctl --since "1 hour ago" -p err`（只读、带行数上限） | JSON |
| `dmesg_tail` | `dmesg -T \| tail -n 200` | JSON |
| `uptime_stats` | `uptime`, `who`, `last` | JSON |

**suggest 层**（只生成建议，不执行）：

| Tool | 作用 |
| --- | --- |
| `root_cause_hypothesis` | 聚合 read_only 结果给出 Top-3 根因假设 |
| `cleanup_plan_generate` | 生成磁盘清理建议（路径 + 预估回收） |
| `tuning_suggestion` | 生成内核/服务参数调优建议 |
| `incident_summary` | 生成可读事件摘要 |

**write_action 层**：**Phase 1 注册为空集**；Policy Guard 对任何 write 调用直接拒绝并告警。

### 6.6 知识库（Knowledge, Phase 1）

```
proagent/domain/server-health-inspector/knowledge/
├── index.md                   # 入口索引
├── domain_overview.md         # 什么是"健康"：阈值与判据
├── thresholds.yaml            # 阈值表（CPU>85% 持续5min ...）
├── runbook_index.md           # 常见问题 runbook 列表
├── system_inventory.md        # 目标主机清单（hostname/IP/role/owner）
├── incident_history.md        # 历史事件库（可检索）
├── glossary.md                # 术语：load1 / iowait / swappiness / …
└── decision_log.md            # 重大判定记录
```

检索策略：**index + on-demand retrieval**；不把 knowledge 一次性塞进 prompt。

### 6.7 用户入口（Phase 1 启用的 Gateways）

| Gateway | 来源 | Phase 1 行为 |
| --- | --- | --- |
| Discord | `gateway/platforms/discord.py` | 主推送 + 问答通道 |
| WeChat (Weixin) | `gateway/platforms/weixin.py` | 问答 + 快速通知（受平台限制） |
| Feishu (飞书) | `gateway/platforms/feishu.py` | 问答 + 巡检报告推送 + 飞书文档输出 |
| REST API | `gateway/platforms/api_server.py` | 内部/外部系统调用 |
| Cron | `cron/` | 定时巡检触发 |
| Webhook | `gateway/platforms/webhook.py` | 监控系统 → Agent |
| CLI | `cli.py` + `hermes_cli/` | 运维本地排查 + 交互式配置 |

其他所有 platform 文件保留但在 `proagent/gateway_profile/phase1.yaml` 中标记 `disabled: true`。

### 6.8 Policy Guard（Phase 1）

```yaml
# proagent/domain/server-health-inspector/policy.yaml
default: deny

allow_auto:
  - read_only.*

allow_auto_with_rate_limit:
  - suggest.*   # 每用户 30次/小时

require_approval:
  - write_action.*   # Phase 1 不注册具体工具，留框架

forbidden:
  - "*.delete_*"
  - "*.drop_*"
  - "*.rotate_secrets*"
  - "*.exec_arbitrary_shell"
  - "*.rm_rf*"

sandbox:
  shell:
    # 采用"开放执行 + 黑名单拦截"策略，不限制具体二进制，
    # 以保证 Agent 可灵活使用任何只读 shell 命令进行诊断。
    # 安全由 denylist_patterns 硬拦截 + read-only 语义校验保证。
    mode: denylist          # allowlist | denylist（Phase 1 使用 denylist 模式）
    denylist_patterns:
      - "rm\\s+"            # 任何 rm 操作
      - "mkfs"
      - "dd\\s+.*of="      # dd 写盘
      - ">[^>]"            # 重定向写文件
      - ">>"               # 追加写文件
      - "curl .* \\| (sh|bash)"
      - "wget .* \\| (sh|bash)"
      - "chmod"
      - "chown"
      - "kill\\s+"
      - "pkill"
      - "shutdown"
      - "reboot"
      - "init\\s+[0-6]"
      - "systemctl\\s+(start|stop|restart|enable|disable|mask)"
      - "service\\s+\\S+\\s+(start|stop|restart)"
      - "iptables"
      - "nft"
      - "mount\\s+"
      - "umount"
      - "fdisk"
      - "parted"
      - "lvremove"
      - "vgremove"
      - "pvremove"
    # 以上模式匹配到即拒绝；未匹配的命令默认允许执行（只读灵活性）
  timeout_sec: 30
  max_output_kb: 256

audit:
  sinks: [sqlite, jsonl]
  fields: [ts, session_id, actor, tool, args_hash, decision, latency, result_hash]
```

**关键保证**：Phase 1 结束时，任何"写"动作都**必然**被 Policy Guard 拦截，工程上而非 Prompt 上保证。

---

## 7. 产品 SPEC（Phase 1）

### 7.1 产品名称

**ProAgent: Server Health Inspector**（代号 `proagent-shi`）

### 7.2 目标用户

- 个人开发者 / 独立站长（单 VPS）
- 小团队 SRE（< 20 台服务器，Phase 1 聚焦单机）
- 内部工具团队（想验证 Agent 能否稳定承接运维值班）

### 7.3 核心功能（MVP）

| # | 功能 | 描述 | 优先级 |
| --- | --- | --- | --- |
| F1 | 定时健康巡检 | Cron 触发，生成结构化巡检报告 | P0 |
| F2 | IM 问答 | Discord / WeChat 自然语言提问，获得分析 | P0 |
| F3 | 问题自动诊断 | 发现异常 → 触发 root_cause_hypothesis → 推送 | P0 |
| F4 | 状态查询 | 用户问 "现在磁盘多少？" 立刻回答 | P0 |
| F5 | 审计日志 | 每次工具调用落表，可查询 | P0 |
| F6 | 只读硬边界 | Policy Guard 拦截任何写操作 | P0 |
| F7 | 多主机（单次一台） | 通过 target 参数指定 SSH 目标 | P1 |
| F8 | 历史趋势问答 | "最近 7 天 CPU 峰值？" | P1 |
| F9 | Runbook 建议 | 基于知识库给出处置建议（不执行） | P1 |
| F10 | Web Dashboard | 最近一次巡检可视化 | P2 |

### 7.4 非功能需求（NFR）

| 维度 | 指标 |
| --- | --- |
| 延迟 | 快问（状态查询） P95 < 8s；深度巡检 P95 < 60s |
| 可用性 | Runtime 进程单点，Phase 1 允许重启恢复；session 持久化不丢 |
| 安全 | 所有 shell 命令走 allowlist；输出脱敏（IP、密钥正则扫描） |
| 成本 | 单台巡检单次 LLM token 花费 < $0.05（默认 gpt-4.1-mini） |
| 可观测 | 结构化日志 + 审计表 + `/status` slash 命令 |
| 可移植 | Linux / macOS 本机模式；SSH 模式支持主流发行版 |

### 7.5 典型交互脚本

**场景 A：定时巡检（Cron → Discord）**

```
[Cron 09:00] → quick_health_check skill
             → 调 host_meta / cpu_snapshot / mem_snapshot / disk_snapshot
             → incident_summary
             → Discord #ops 频道推送结构化卡片
```

Discord 输出示例：

```
☤ 早安健康报告 · web-01 · 2026-05-11 09:00
状态：🟡 注意
- CPU load1 2.3（阈值 2.0）
- /var 使用 82%（阈值 80%）
- 无 failed units
Top 嫌疑：nginx access log 未轮转。
建议：查看 /var/log/nginx，考虑 logrotate（仅建议，未执行）。
[详情] [追问] [7 天趋势]
```

**场景 B：WeChat 问答**

```
用户: web-01 现在怎么样？
Agent: （read_only snapshot, 结构化摘要）
用户: 为什么磁盘高？
Agent: → disk_pressure_diagnose skill
       → root_cause_hypothesis
       返回 Top-3 假设 + 证据 + 建议（不执行）
```

**场景 C：Webhook → 自动诊断**

```
Alertmanager → POST /webhook/alert (payload: disk > 90%)
            → Router 识别 target=web-01 / kind=disk_pressure
            → 触发 disk_pressure_diagnose
            → 自动产出报告推 Discord + 存 incident_history.md
```

### 7.6 数据模型（关键表）

```sql
-- session（复用 Hermes sessions.db）
-- 新增：
CREATE TABLE inspection_run (
  id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  kind TEXT NOT NULL,        -- quick | full | diagnose
  trigger TEXT NOT NULL,     -- cron | user | webhook
  started_at INTEGER NOT NULL,
  ended_at INTEGER,
  status TEXT NOT NULL,      -- running | ok | warn | error
  summary TEXT,
  report_json TEXT
);

CREATE TABLE audit_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  session_id TEXT,
  actor TEXT NOT NULL,        -- user / agent / cron
  domain TEXT NOT NULL,
  tool TEXT NOT NULL,
  args_hash TEXT NOT NULL,
  decision TEXT NOT NULL,     -- allow | deny | approval_required
  reason TEXT,
  latency_ms INTEGER,
  result_hash TEXT
);
```

### 7.7 配置样例

```yaml
# proagent.yaml
runtime:
  domain: server-health-inspector
  locale: zh-CN

models:
  planner:    { provider: openai,    model: gpt-4.1-mini }
  executor:   { provider: openai,    model: gpt-4.1-mini }
  summarizer: { provider: anthropic, model: claude-3-5-haiku }

gateways:
  discord:
    enabled: true
    channels: [ops]
  weixin:
    enabled: true
  feishu:
    enabled: true
    app_id: cli_xxxxx
    app_secret: ${FEISHU_APP_SECRET}
  api:
    enabled: true
    bind: 127.0.0.1:8787
  cron:
    enabled: true
    jobs:
      - { name: hourly-quick,   cron: "0 * * * *",  skill: quick_health_check }
      - { name: daily-full,     cron: "0 9 * * *",  skill: full_health_inspection }

targets:
  default: local
  hosts:
    - { id: local, backend: local }
    - { id: web-01, backend: ssh, host: 10.0.0.11, user: ops, keyfile: ~/.ssh/id_ed25519 }

policy:
  pack: default   # 加载 domain 自带 policy.yaml

audit:
  db: proagent/storage/audit.db
```

### 7.8 CLI 交互式配置（Setup Wizard）

ProAgent 保留并增强 Hermes 的 CLI 交互式配置能力，用户通过命令行完成首次部署和日常变更，无需手动编辑 YAML。

#### 7.8.1 模型配置（`proagent model`）

复用 Hermes `hermes model` 的交互式选择体验，收敛为 ProAgent 支持的 adapter 范围：

```bash
# 交互式模型配置向导
proagent model

# 直接设置（非交互）
proagent model set planner openai:gpt-4.1-mini
proagent model set executor openai:gpt-4.1-mini
proagent model set summarizer anthropic:claude-3-5-haiku

# 查看当前模型配置
proagent model show

# 测试模型连通性
proagent model test
```

交互式流程：

```
$ proagent model
┌─ ProAgent 模型配置 ─────────────────────────────┐
│                                                  │
│  当前 Domain: server-health-inspector            │
│                                                  │
│  选择角色:                                       │
│  > [1] planner   (任务规划)                      │
│    [2] executor  (工具执行)                      │
│    [3] summarizer(结果摘要)                      │
│    [4] verifier  (结果校验)                      │
│    [5] 全部重新配置                              │
│                                                  │
│  选择 Provider:                                  │
│  > [1] openai                                    │
│    [2] anthropic                                 │
│    [3] minimax (可选)                            │
│    [4] moonshot (可选)                           │
│                                                  │
│  输入 API Key: sk-***                            │
│  选择 Model: gpt-4.1-mini                        │
│                                                  │
│  ✓ 连通性测试通过 (latency: 320ms)              │
│  ✓ 已写入 proagent.yaml                         │
└──────────────────────────────────────────────────┘
```

#### 7.8.2 服务器接入配置（`proagent target`）

新增 CLI 命令，交互式引导用户添加、测试、管理被巡检的目标服务器：

```bash
# 交互式添加目标服务器
proagent target add

# 直接添加（非交互）
proagent target add --id web-01 --backend ssh --host 10.0.0.11 --user ops --keyfile ~/.ssh/id_ed25519

# 添加本地目标
proagent target add --id local --backend local

# 列出所有目标
proagent target list

# 测试目标连通性
proagent target test web-01

# 测试所有目标
proagent target test --all

# 移除目标
proagent target remove web-01

# 设置默认目标
proagent target default web-01
```

交互式流程：

```
$ proagent target add
┌─ 添加巡检目标 ──────────────────────────────────┐
│                                                  │
│  目标 ID: web-01                                 │
│                                                  │
│  连接方式:                                       │
│  > [1] local  (本机)                             │
│    [2] ssh    (SSH 远程)                         │
│    [3] docker (Docker exec)                      │
│                                                  │
│  ── SSH 配置 ──                                  │
│  主机地址: 10.0.0.11                             │
│  SSH 端口 [22]: 22                               │
│  用户名: ops                                     │
│  认证方式:                                       │
│  > [1] SSH Key                                   │
│    [2] Password                                  │
│  Key 路径 [~/.ssh/id_ed25519]: ~/.ssh/id_ed25519 │
│                                                  │
│  ── 连通性测试 ──                                │
│  ✓ SSH 连接成功                                  │
│  ✓ 基础命令可执行 (uname, free, df)              │
│  ✓ 目标 OS: Ubuntu 22.04 LTS (x86_64)           │
│  ⚠ smartctl 未安装（SMART 巡检将跳过）           │
│                                                  │
│  ── 可选标签 ──                                  │
│  角色 [web/db/app/custom]: web                   │
│  负责人: zhangsan                                │
│  备注: 生产 Web 前端                             │
│                                                  │
│  ✓ 已添加到 proagent.yaml → targets.hosts        │
└──────────────────────────────────────────────────┘
```

连通性测试自动检测：

| 检测项 | 说明 |
| --- | --- |
| SSH 握手 | 验证网络可达 + 认证通过 |
| 基础命令 | 执行 `uname -a`, `free -m`, `df -h` 确认权限 |
| OS 识别 | 读取 `/etc/os-release` 自动识别发行版 |
| 工具可用性 | 检测 `smartctl`, `iostat`, `mpstat` 等可选工具是否安装 |
| sudo 权限 | 检测是否有 `sudo` 且是否需要密码（部分工具如 `smartctl` 需要） |

测试结果写入 `knowledge/system_inventory.md`，Agent 后续巡检时自动跳过不可用的工具。

#### 7.8.3 一键初始化（`proagent setup`）

整合模型 + 目标 + Gateway 的完整初始化向导：

```bash
proagent setup
# 依次引导：
# 1. 选择 Domain Pack
# 2. 配置模型（planner / executor / summarizer）
# 3. 添加目标服务器（至少一台）
# 4. 配置 Gateway（Discord token / WeChat / Feishu）
# 5. 生成 proagent.yaml
# 6. 运行首次巡检验证
```

### 7.9 指标与可观测

- `proagent.inspection.runs_total{status,target,kind}`
- `proagent.tool.calls_total{tool,decision}`
- `proagent.llm.tokens_total{role}`（planner/executor/summarizer）
- `proagent.policy.denied_total{tool,reason}`
- `/status` slash 命令：返回 Runtime 版本、Pack、近 24h 指标

---

## 8. 里程碑与演进路线

### Phase 1 — ProAgent Runtime + Server Health Inspector（MVP）

**目标**：端到端跑通"单机只读巡检 + IM 问答"，验证架构。

- M1.1 仓库整理：新建 `proagent/` 根目录，设计骨架，确定依赖收敛
- M1.2 Gateway 精简：启用 Discord / WeChat / Feishu / API / Cron / Webhook / CLI；其他标记 disabled
- M1.3 Policy Guard v1：denylist 模式 + 审计表
- M1.4 Domain Pack 加载器：读取 `pack.yaml` 装配 knowledge / skills / tools
- M1.5 工具集：实现 read_only shell 执行器（denylist 守护）+ 4 个 suggest 工具
- M1.6 Skills：9 个只读 SOP 技能
- M1.7 巡检流程：Cron 路径 + Webhook 路径 + IM 问答路径
- M1.8 审计：`audit_event` / `inspection_run` 表
- M1.9 CLI 配置向导：`proagent model` / `proagent target` / `proagent setup`
- M1.10 联调：本地 + SSH 目标
- M1.11 文档：用户指南、Domain Pack 开发指南、Policy 编写指南

### Phase 2 — 多主机 + 权限分级 + 审批流

- 多主机清单与拓扑
- `write_action` 工具（重启服务、清日志、滚动等）+ 审批流
- 任务状态机（pending / approved / executing / done / failed / rolled_back）

### Phase 3 — Skill 自动生成 + Human Review

- Curator 建议生成新 Skill → PR 式审核合并
- Skill 版本化、A/B、回滚

### Phase 4 — Multi-Agent

- Planner / Executor / Verifier / Reporter 分工
- Cross-domain 协作（SRE + DBA）

### Phase 5 — 新领域 Pack 复制

- Testing Pack（仓库读 / 失败用例诊断 / 生成测试建议）
- Finance Pack（只读财报 / 对比 / 报告）
- DBA Pack（慢查询 / 统计信息 / 建议索引）

---

## 9. 验收标准（DoD）

Phase 1 完成需满足以下全部条件：

1. 从零部署在一台 Ubuntu 22.04 VPS，执行 `proagent run` 后：
   - Cron 按配置触发巡检并推送到 Discord
   - 在 Discord / WeChat 发送 `web-01 状态如何？` 得到结构化回答 < 10s
2. 触发任何 write 动作（例如人为构造一个恶意 prompt 让模型尝试 `rm -rf`）必被 Policy Guard 拦截并审计
3. `audit_event` 表记录每一次工具调用，字段完整
4. 连续运行 24h 无 OOM / 无句柄泄漏，巡检失败率 < 1%
5. 切换 Domain Pack（即便是一个 Hello-World Pack）能生效，证明 Runtime 与 Domain 解耦
6. 文档齐全：部署指南、Pack 开发指南、Policy 编写指南、故障排查手册
7. 基本回归测试：`proagent/domain/server-health-inspector/tests/` 覆盖 9 个 Skills 的干跑

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Hermes 代码耦合度高，裁剪引入回归 | 中 | 采用"禁用优先，不删除"；在 `proagent/` 建新层，不污染 `agent/` 核心 |
| LLM 幻觉给出错误诊断 | 高 | suggest 层必须引用 evidence（工具输出片段）；Verifier 模型做二次校验 |
| shell 命令注入 | 高 | allowlist + 参数化 + `shlex.quote`；禁止管道到 `sh` |
| WeChat/Weixin 平台限制 | 中 | 第一优先保证 Discord 通路，Weixin 作为次要通道 |
| 审计表膨胀 | 低 | 按 session/日期归档，保留 90 天滚动 |
| 模型 Token 成本失控 | 中 | planner/executor 默认 mini 档；对 summarizer 做 token 预算 |
| 用户希望"一键修复" | 高 | 明确 Phase 1 只读承诺；Phase 2 引入审批流再开放 |

---

## 11. 附录

### 11.1 新增目录建议（首次落地）

```
hermes-agent/
├── proagent/
│   ├── __init__.py
│   ├── core/
│   │   ├── runtime.py
│   │   ├── task_router.py
│   │   └── loader.py
│   ├── policy/
│   │   ├── guard.py
│   │   ├── audit.py
│   │   └── sandbox.py
│   ├── domain/
│   │   └── server_health_inspector/
│   │       ├── pack.yaml
│   │       ├── system_prompt.md
│   │       ├── knowledge/
│   │       ├── skills/
│   │       ├── tools/
│   │       ├── policy.yaml
│   │       └── tests/
│   ├── gateway_profile/
│   │   └── phase1.yaml
│   └── cli/
│       └── main.py
├── docs/
│   ├── RedesignHermes.md            (保留，作为初稿)
│   └── ProAgent-Redesign-Plan.md    (本文档)
└── ... (Hermes 原结构保留)
```

### 11.2 与 Hermes 现有代码的映射

| ProAgent 新模块 | 复用的 Hermes 资产 |
| --- | --- |
| `proagent/core/runtime.py` | `agent/curator.py`, `agent/context_engine.py` |
| `proagent/core/task_router.py` | `gateway/session.py`, `gateway/delivery.py` |
| `proagent/policy/guard.py` | `tools/approval.py`, `tools/file_safety.py`, `tools/path_security.py` |
| `proagent/policy/audit.py` | `hermes_state.py`（session/audit 底座） |
| Skills/Tools 打包 | `tools/registry.py`, `tools/skills_*`, `skills/` |
| Gateway 精简 | `gateway/platform_registry.py` + `gateway_profile/phase1.yaml` |
| 多后端执行 | `tools/environments/`（local / ssh / docker …） |

### 11.3 后续需要决策的开放问题

- [ ] WeChat 通路的合规与稳定性选型（官方客服号 / 企业微信 / 第三方协议）
- [ ] 审批流 UI：Phase 2 走 Discord 交互按钮 or 独立 Web？
- [ ] 知识库是否引入向量检索，还是先纯 BM25 + 关键词 index？
- [ ] 是否在 Phase 1 就引入 OpenTelemetry？（建议：引入 tracer 占位符，不强制导出）
- [ ] Domain Pack 是否支持远程仓库订阅与签名验证？（Phase 3+）

---

**文档状态**：Draft v0.1 → **Phase 1 已完成** · Phase 2 计划见 `docs/ProAgent-Phase2-Plan.md`

### Phase 1 完成记录（2026-05-11）

已交付：
- `proagent/` 完整代码（core/policy/domain/cli）
- 独立 Agent 循环（不依赖 Hermes run_agent.py）
- MiniMax CN / OpenAI / Anthropic 三 Provider 支持
- SSH 连接池（Windows 兼容）
- Policy Guard 57 条 denylist 规则
- SQLite 审计
- Discord Gateway（含代理支持）
- `--verbose` 执行追踪
- 代码精简（删除 66 文件 / 57k LOC）
- 人工测试指南（`docs/ProAgent-Manual-Test.md`）

分支：`feature/proagent-redesign`

### Test Agent 完成记录（2026-05-12）

已交付：
- **Test Agent Domain Pack** (`proagent/domain/test_agent/`)
  - AI 驱动的测试用例生成、执行、分析与报告
  - 支持 Python/TypeScript/JavaScript/Go/Java/Rust
  - 支持单元/功能/API/UI/性能测试类型
- **AIGC Image Generation Tests** (`proagent/domain/test_agent/tests/test_aigc_image_generation.py`)
  - 20 个测试用例覆盖成功路径、错误处理、参数验证、安全、输出格式
  - 18 个单元测试通过，2 个集成测试需真实 API Key
- **SRE Agent Tests** (`proagent/domain/test_agent/tests/test_sre_server_shell.py`)
  - 测试 Policy Guard 的 allow/deny 规则
  - 测试 SSH Pool 本地模式
  - 测试 Runtime 集成
- **Domain Pack 配置**
  - `max_iterations: 50` (测试 Agent 需要更多迭代轮次)
  - `max_test_steps: 100` (测试执行工作流最大步数)
  - `requires_ssh: false` (本地测试不需要 SSH)
- **Agent Loop 增强**
  - 支持从 `pack.yaml` 配置 `max_iterations`
  - 改进错误消息显示实际迭代限制
  - 修复 `resolve_provider` 导入问题

### Phase 4 完成记录（2026-05-12）

**目标**：完成三个 Agent（SRE/AIGC/Test）的产品化能力闭环 + 统一 GUI 入口。

#### M4.1-M4.3: SRE Agent 写操作白名单 ✅

- **`proagent/policy/guard.py`** 新增 `write_action_whitelist` 字段（`PolicyConfig`）
  - `check_tool` 优先检查 write_action 白名单：在内的允许，否则一律 DENY
  - 默认空白名单 → 维持 Phase 1 严格 read-only 行为
- **`proagent/core/agent.py`** ToolDef 新增 `category` 字段（read_only/suggest/write_action）
  - ProAgent 接收 `policy_guard` 参数；执行每个工具前调用 `check_tool` 强制策略
- **`proagent/domain/server_health_inspector/tools/write_report.py`** 新增两个工具
  - `write_diagnosis_report(target, summary, evidence, severity, suggested_steps)`
  - `write_inspection_report(target, kind, summary, metrics, issues)`
  - 输出到 `proagent/storage/reports/diagnosis-*.md` 和 `inspection-*.md`
  - 文件名包含时间戳 + slug，避免覆盖
- **`policy.yaml`** SRE 包：`write_action_whitelist: [write_diagnosis_report, write_inspection_report]`
- **`system_prompt.md`** 注入自动诊断 SOP 与定期巡检流程
- **测试**：`test_sre_phase4.py` 25 个用例全部通过

#### M4.4-M4.6: AIGC Agent 提示词优化 + 多图生成 + 历史 ✅

- **`prompt_optimize`**（suggest 类）：10 种风格预设（auto/photo/anime/oil-painting/watercolor/concept-art/3d-render/minimalist/cyberpunk/pixar）+ 质量增强器 + 默认负面提示词
- **`image_generate_batch`**（write_action）：单次最多 8 张，每张独立 seed，结果记录到 `aigc_history.db`
- **`image_history_list`**（read_only）：最近 N 条生成记录的 markdown 表格
- **`image_feedback`**（write_action）：用户评分 best/good/bad 写入 SQLite
- **`policy.yaml`** AIGC 包：白名单 `aigc_generate / image_generate_batch / image_feedback`
- **测试**：`test_aigc_phase4.py` 26 个用例全部通过（mock 化 mmx 调用）

#### M4.7-M4.9: Test Agent 代码扫描 + PRD 解析 ✅

- **`code_scan`**（read_only）：递归扫描项目，识别 Python/TS/JS/Go/Rust/Java 源文件，统计可测试单元（公共 function + class），按数量降序排序，自动跳过 vendor 目录与已存在测试
- **`prd_parse`**（read_only）：解析 markdown PRD，提取 EARS 验收条件 / 用户故事 / Bullet 功能列表 / 需求章节
- **`policy.yaml`** Test 包：白名单 `report_generate`；明确禁止 `aigc_generate / image_generate_batch / server_shell`
- **测试**：`test_test_agent_phase4.py` 18 个用例全部通过

#### M4.10-M4.11: 统一 Streamlit GUI ✅

- **`proagent/gui/app.py`**：基于 Streamlit 的统一控制中心
  - 侧边栏：三 Agent 切换（SRE/AIGC/Test）
  - 四个面板：💬 对话 · 📋 报告库 · 🖼️ 图片画廊 · ⚙️ 状态
  - 对话面板：多轮对话 + 新会话按钮 + per-agent session
  - 报告库：自动展示 SRE 写入的 markdown 报告，支持选择查看
  - 图片画廊：从 `aigc_history.db` 读取生成历史，缩略图布局
  - 状态面板：当前 Agent / 模型 / API Key / Policy Guard 配置
- **`proagent/cli/main.py`**：新增 `gui` 子命令
  - `python proagent_run.py gui --port 8501 --host localhost`
  - 自动委托给 `streamlit run`
- **测试**：`test_gui.py` 7 个用例全部通过（导入 + helper + CLI dispatch）

#### M4.12: E2E 验证 ✅

`pytest proagent/domain/test_agent/tests/`: **110 passed, 2 skipped, 0 failed**

按 Phase 4 Agent 分布：
- SRE Phase 4：25 用例 PASS
- AIGC Phase 4：26 用例 PASS
- Test Agent Phase 4：18 用例 PASS
- GUI：7 用例 PASS
- 原有测试（Phase 1/2/3）：34 用例 PASS（2 skipped 需真实 API Key）

#### 入口与使用

```bash
# CLI 交互式（任一 agent）
python proagent_run.py domain use server-health-inspector
python proagent_run.py run -v

# 切换到 AIGC
python proagent_run.py domain use aigc-creator
python proagent_run.py run -v

# 切换到 Test
python proagent_run.py domain use test-agent
python proagent_run.py run -v

# 启动统一 GUI（推荐）
python proagent_run.py gui
# 浏览器访问 http://localhost:8501
```

#### 与"真正产品"的剩余差距

下一阶段（Phase 5）应聚焦：
1. 多用户 Auth / RBAC（当前是单进程单用户）
2. Session 持久化（重启后历史保留）
3. Discord 审批按钮（当前 GUI 无审批流，仅本地策略）
4. Prometheus metrics + OpenTelemetry trace
5. Docker / docker-compose 部署清单
6. Provider fallback（当前单 provider 失败即整体失败）
7. PII 脱敏 + 密钥轮换
8. Cron 定时巡检写报告 + Discord 推送（M4.3 框架已就绪，仅需配置）

---

## 12. Phase 4 计划：三 Agent 闭环 + 统一 GUI 入口

> 版本: v0.4 (2026-05-12)
> 目标: 完成 SRE / AIGC / Test 三个 Agent 的产品化能力闭环，提供统一 GUI 入口，进入"可演示、可迭代"产品形态

### 12.1 三 Agent 产品需求

#### 12.1.1 SRE Agent（自动诊断 + 定期巡检）

**当前状态**：✅ 只读巡检 + Policy Guard 已实现

**Phase 4 需补齐**：
- ✅ 自动诊断流程（需求→工具调用→根因→修复步骤）
- ✅ 故障排查 SOP（disk_pressure / memory / cpu / network / service / log）
- ✅ 定期巡检 Cron + 报告
- 🆕 **白名单写操作**：仅允许两个写动作
  - `write_diagnosis_report(target, summary, evidence)` → 写入 `proagent/storage/reports/diagnosis-<ts>.md`
  - `write_inspection_report(target, kind, summary)` → 写入 `proagent/storage/reports/inspection-<ts>.md`
- 🆕 Policy Guard 写操作白名单：除上述两个工具外，所有 write_action 仍被拦截
- 🆕 修复步骤生成：在诊断报告中输出建议命令（仅 suggest，不执行）

**Domain Pack 调整**：
```yaml
# proagent/domain/server_health_inspector/pack.yaml
capabilities:
  read_only: true
  suggest:   true
  write_action: true   # 改为 true，但严格白名单
  write_action_whitelist:
    - write_diagnosis_report
    - write_inspection_report
```

#### 12.1.2 AIGC Agent（提示词优化 + 多图生成）

**当前状态**：✅ MiniMax CLI 工具调用已通

**Phase 4 需补齐**：
- 🆕 **提示词优化器**：用户给出 idea → LLM 优化为高质量 prompt（含风格、构图、光照等元素）
- 🆕 **多图生成**：单次最多 8 张图片（变体不同 seed/aspect_ratio/style）
- 🆕 **图片预览展示**：返回缩略图链接 + 元数据
- 🆕 **生成历史记录**：保存 prompt + 生成参数 + 输出路径到 SQLite
- 🆕 **图片选择反馈**：用户标记 best/good/bad → 用于后续 prompt 学习

**新工具**：
- `prompt_optimize(idea: str, style: str = "auto") -> optimized_prompt`
- `image_generate_batch(prompt: str, count: int = 4, max: 8) -> list[image_path]`
- `image_history_list(limit: int = 20) -> list[record]`
- `image_feedback(image_id: str, rating: str)`  # best/good/bad

#### 12.1.3 Test Agent（自动测试 + 报告）

**当前状态**：✅ 测试用例已能为 AIGC/SRE 生成

**Phase 4 需补齐**：
- 🆕 **代码扫描器**：递归读取项目 → 识别可测试模块 → 生成测试矩阵
- 🆕 **产品手册解析**：读取 PRD/markdown → 提取测试需求
- 🆕 **测试用例覆盖率报告**：以表格形式呈现已覆盖/未覆盖
- 🆕 **回归测试自动化**：监控代码变更 → 自动 rerun 相关测试
- 🆕 **测试报告输出**：HTML/Markdown 格式包含通过率、失败用例、覆盖率

**新工具**：
- `code_scan(path: str) -> module_list`
- `prd_parse(path: str) -> requirement_list`
- `test_generate(target: str, prd: str = "") -> test_file_path`
- `test_run(test_path: str) -> result`
- `coverage_report(test_path: str) -> coverage_data`

### 12.2 统一 GUI 入口（新增）

**当前**：只有 CLI（`python proagent_run.py run`）

**Phase 4 目标**：基于 Web 的统一 GUI，支持三个 Agent 切换、对话、报告查看

**技术栈**：
- 后端：FastAPI（已有 api_server gateway）扩展
- 前端：Streamlit（最简）或 React（更灵活）
- 通信：WebSocket（实时 streaming）+ REST（历史数据）

**界面布局**：
```
┌────────────────────────────────────────────────────┐
│  ProAgent 控制中心                                 │
├──────────┬─────────────────────────────────────────┤
│ Agent    │  对话区                                 │
│ ────     │  ┌──────────────────────────────────┐   │
│ 🔧 SRE   │  │ 用户: 检查 web-01 磁盘            │   │
│ 🎨 AIGC  │  │                                   │   │
│ 🧪 Test  │  │ 🤖 (verbose: tool calls...)      │   │
│ ────     │  │                                   │   │
│ 历史会话  │  └──────────────────────────────────┘   │
│ 报告库   │  [输入框]                    [发送]     │
│ 配置     │                                         │
└──────────┴─────────────────────────────────────────┘
```

**核心功能**：
1. 三 Agent 一键切换
2. Verbose 模式（工具调用可视化）
3. 报告库：浏览/下载诊断/巡检/测试报告
4. AIGC 图片画廊
5. 历史会话回看
6. 模型/Target/Policy 配置面板

### 12.3 Phase 4 里程碑

| # | 里程碑 | 交付物 | 状态 |
|---|--------|--------|------|
| M4.1 | SRE 写操作白名单 | `write_diagnosis_report` + `write_inspection_report` 工具 + Policy 白名单 | 待实现 |
| M4.2 | SRE 自动诊断 SOP | 故障排查模板（disk/mem/cpu/net/service/log）→ Skills 文件 | 待实现 |
| M4.3 | SRE 定期巡检 | Cron 触发 → 巡检 → 写报告 → Discord 推送 | 待实现 |
| M4.4 | AIGC 提示词优化器 | `prompt_optimize` 工具 + 风格库 | 待实现 |
| M4.5 | AIGC 多图生成 | `image_generate_batch` 工具，最多 8 张 | 待实现 |
| M4.6 | AIGC 历史 + 反馈 | SQLite 记录 + 评分接口 | 待实现 |
| M4.7 | Test 代码扫描 | `code_scan` 工具 + 测试矩阵生成 | 待实现 |
| M4.8 | Test PRD 解析 | `prd_parse` 工具 | 待实现 |
| M4.9 | Test 覆盖率报告 | 集成 coverage.py + 表格报告 | 待实现 |
| M4.10 | GUI 后端 API | FastAPI 扩展三 Agent endpoint | 待实现 |
| M4.11 | GUI 前端 | Streamlit 实现统一界面 | 待实现 |
| M4.12 | E2E 验证 | Test Agent 测试三个 Agent 各自闭环 | 待实现 |
| M4.13 | 文档与样例 | 三 Agent 用户手册 + GUI 演示视频 | 待实现 |

### 12.4 与"真正产品"的差距（Gap Analysis）

| 维度 | 当前状态 | 产品要求 | 差距 |
|------|---------|---------|------|
| **稳定性** | 单进程，无重启恢复 | 7×24 运行 + 故障自恢复 | 进程守护 + 健康检查 + Session 持久化 |
| **多用户** | 单 session | 多用户多会话隔离 | Auth + Session 命名空间 + 配额 |
| **权限管理** | 全开 | RBAC（admin/user/viewer） | 角色矩阵 + 操作审批 |
| **可观测** | 文本日志 | Metrics/Trace/Log 三件套 | Prometheus + OpenTelemetry |
| **安全** | API key 明文 | 密钥管理 | Vault/KMS 集成 |
| **部署** | 本地 Python | 容器化 + 编排 | Dockerfile + docker-compose + K8s manifest |
| **测试** | 单元 + 集成 | E2E + 性能 + 安全 | Playwright/k6/OWASP ZAP |
| **CI/CD** | 无 | 自动化构建 + 部署 | GitHub Actions + 制品库 |
| **文档** | 开发文档 | 用户/运维/API 三类 | 用户手册 + 运维 Runbook + OpenAPI |
| **国际化** | 中文 | 中英双语 | i18n 资源 + 切换 |
| **计费/配额** | 无 | 按 token/调用次数 | 计量 + 阈值告警 |
| **LLM 容错** | 单点失败 | 多 provider fallback | Provider 降级链 |
| **数据隐私** | 无脱敏 | PII 检测 + 脱敏 | 正则扫描 + masking |

### 12.5 Phase 4 验收标准（DoD）

1. SRE Agent 完成一次完整诊断（输入告警 → 自动诊断 → 输出报告 → 写入 storage）
2. SRE Agent 尝试任何非白名单写操作（除两个 report 外）必被 Policy Guard 拦截
3. AIGC Agent 接受用户 idea → 优化 prompt → 生成 4-8 张图片 → 用户可评分
4. Test Agent 扫描一个项目 → 生成 ≥ 10 个测试用例 → 执行 → 输出覆盖率报告
5. GUI 在浏览器中展示三 Agent 入口，可切换、可对话、可查看历史
6. Test Agent 用 e2e 测试覆盖三 Agent 主流程（≥ 30 个测试用例，通过率 100%）
7. 文档：每个 Agent 有 5 分钟 Quick Start 用户手册
8. 单台机器连续运行 24h 无内存泄漏、无连接泄漏

### 12.6 Phase 4 执行顺序（建议）

**Week 1**: SRE Agent 写操作白名单 + 自动诊断 SOP（M4.1-M4.3）

**Week 2**: AIGC Agent 提示词优化 + 多图生成（M4.4-M4.6）

**Week 3**: Test Agent 代码扫描 + PRD 解析 + 覆盖率（M4.7-M4.9）

**Week 4**: GUI 后端 + 前端 + E2E 验证（M4.10-M4.13）

---

**API Key 配置（local only, .env）**：
```bash
# .env
MINIMAX_CN_API_KEY=sk-cp-...（已配置）
```

下一会话计划：使用 Test Agent 自动验证三个 Agent 是否满足 Phase 4 要求，迭代直到全部通过。

---

## 13. Phase 5 计划：四 Agent 产品化 + 7x24 Discord Gateway

> 版本: v0.5 (2026-05-20)
> 目标: 在现有 SRE / Test / AIGC 三 Agent 基础上新增 **Develop Agent**，形成"需求/PRD → 开发 → 测试 → 运维反馈"闭环；同时把 Discord 与 Web UI 升级为 7x24 可用入口与可观测控制台。

### 13.1 Agent 关系与职责边界

| Agent | 职责 | 主要入口 | 是否需要 Web UI | 权限边界 |
| --- | --- | --- | --- | --- |
| SRE Agent | Lab SRE：Storage / GPU server / K8S 的巡检、状态检查、故障排查、报告生成 | Discord `/sre`、Web UI、Cron | 是 | 默认 read_only + 报告写入白名单；未来 write_action 必须审批 |
| Test Agent | 按 PRD/需求验证 SRE Agent、AIGC Agent、Develop Agent 的行为；运行真实测试、单元测试、回归测试并出测试报告 | Discord `/test`、Web UI、CI/local test runner | 是 | 只能读项目、生成测试/报告、执行明确测试命令；不能改业务代码 |
| AIGC Agent | 娱乐与创作：图片/内容生成，不参与 SRE 产品闭环 | Discord `/aigc` | 否，独立轻量入口即可 | 仅允许 AIGC 相关工具与历史反馈；与 SRE/Test/Develop 隔离 |
| Develop Agent | Feature / bugfix driven：开发 SRE Agent 自身能力、修复缺陷、更新代码与文档 | Discord `/develop`、Web UI、CLI | 是 | 可改代码，但必须由需求/PRD/issue 驱动；关键变更经 Test Agent 验证 |

命名约定：统一落地为 **Develop Agent**，Discord slash 使用 `/develop`。

### 13.2 目标工作流

```
需求 / PRD / SRE 事故复盘
        │
        ▼
Develop Agent 设计与实现 feature/bugfix
        │
        ▼
Test Agent 基于需求运行真实测试 / 单元测试 / 回归测试
        │
        ▼
SRE Agent 在 lab 环境巡检 / 排障 / 记录历史
        │
        └── 发现缺陷或新需求 → 回到 Develop Agent
```

要求：
- 所有 feature 级代码变更必须能追溯到 PRD、requirement、bug report 或 phase milestone。
- Develop Agent 不能直接把"想到的优化"当作需求；必须先更新 `docs/ProAgent-Redesign-Plan.md` 或当前 phase doc。
- Test Agent 对每个 feature/bugfix 产出测试结论：测试命令、通过/失败状态、失败证据、未覆盖风险。
- SRE Agent 的 troubleshooting / check status session 必须进入历史库，供 Web UI 回看、搜索和复盘。

### 13.3 Web UI 要求

SRE Agent、Test Agent、Develop Agent 需要统一 Web UI；AIGC Agent 不纳入主控制台，只在 Discord 使用。

核心页面：
- **Session History**：按 agent / target / status / date 查询历史会话；展示 SRE troubleshooting、check status、Develop implementation、Test execution 的完整摘要和工具调用证据。
- **SRE Operations**：目标服务器、Storage、GPU server、K8S 状态；最近巡检；最近事故；报告库。
- **Develop Board**：Develop Agent 当前 feature/bugfix、关联 PRD/phase doc、改动文件、实现状态、阻塞点、关联测试。
- **Test Dashboard**：测试用例、测试状态、最近运行、失败详情、覆盖需求矩阵。
- **Token Usage**：按 agent/session/provider/model 统计 input/output/cache/reasoning token、估算成本和每日预算消耗。

数据落地建议：
- `proagent/storage/session_history.db`：消息、session、agent、target、summary、tool events。
- `proagent/storage/work_items.db`：需求、feature、bugfix、实现状态、测试状态。
- `proagent/storage/usage.db`：LLM usage 归一化记录。
- 可先复用 SQLite，等 7x24 多实例部署稳定后再迁移 PostgreSQL。

### 13.4 Discord Gateway 要求

Discord 是 7x24 主入口，后续与 agent/gateway 一起 Docker 部署。

Slash 交互：
- `/aigc <prompt>`：切换或发送到 AIGC Agent。
- `/test <request>`：发送到 Test Agent，支持运行测试、查看测试状态。
- `/develop <request>`：发送到 Develop Agent，创建/继续 feature 或 bugfix work item。
- `/sre <request>`：发送到 SRE Agent，执行巡检、排障、状态查询。
- `/agent status`：显示各 Agent 运行状态、当前 session、最近错误。
- `/agent switch <aigc|test|develop|sre>`：设置当前 channel/thread 默认 Agent。

运行要求：
- Gateway 进程必须支持 7x24 长跑：自动重连、心跳、异常隔离、日志轮转、健康检查端点。
- 每个 Discord channel/thread 绑定独立 session context，避免不同 Agent 的上下文污染。
- Docker 部署需提供 `Dockerfile`、`docker-compose.yml`、`.env.example`、健康检查和持久卷。

### 13.5 Hermes 裁剪与归档策略

目标不是一次性删除 Hermes，而是把无关能力移入 `archive/` 或禁用路径，保留让 Agent 更聪明的核心资产。

优先保留：
- Agent loop / provider adapter / prompt builder 中与 tool calling、structured output、streaming、usage 捕获相关的代码。
- Memory：`agent/memory_manager.py`、`agent/memory_provider.py`、memory plugins 的接口思想；ProAgent 需要按 user/team/lab/target 分层记忆。
- Skills：`agent/skill_*`、`tools/skills_*`、`tools/skill_manager_tool.py`、`tools/skill_usage.py`、curator 的安全生命周期思想。
- Session search / history：`hermes_state.py` 的 SQLite + FTS5 思路，迁移为 ProAgent session history。
- Gateway：Discord platform、api_server、webhook、session_context、restart/status 相关能力。
- Usage pricing：`agent/usage_pricing.py` 和 transports 中 usage normalizer 的实现，用于 ProAgent token tracking。
- Tool registry / guardrails：`tools/registry.py`、`agent/tool_guardrails.py`、approval/path safety 相关能力。

优先归档或禁用：
- 非目标平台入口：Telegram、Slack、WhatsApp、Signal、Matrix、Mattermost、SMS、HomeAssistant、DingTalk、QQ 等，除非后续 phase 明确需要。
- 娱乐/媒体工具从 SRE/Test/Develop 默认 toolset 移除，仅 AIGC Pack 可用。
- RL、benchmark、website 文档站、TUI 大量上游兼容层先移入 archive 或保持禁用，不进入 ProAgent runtime 默认路径。

归档规则：
- 不直接删除仍有引用的代码；先通过 import/test 验证引用链。
- 归档必须更新 AGENTS.md、phase doc、README 中的路径说明。
- 每次归档后由 Test Agent 跑最小回归：domain load、policy guard、Discord gateway import、GUI import。

### 13.6 Skills 自动创建要求

ProAgent 需要保留并改造 Hermes 的 Skill 能力，让 Agent 能自动沉淀 SOP。

要求：
- SRE Agent 在重复排障流程、频繁查询序列、新事故类型出现时，提出 skill draft。
- Develop Agent 可把已验证的 feature/bugfix 工作流沉淀为 develop skill。
- Test Agent 为每个 skill draft 生成 dry-run 测试和最小回归用例。
- Skill 自动创建必须是 draft-first：自动生成 `SKILL.md` 草稿、引用 evidence、标记来源 session，经用户或 reviewer approve 后才启用。
- Skill 文件需要版本、owner、适用 Agent、允许工具、停止条件、测试命令、回滚方式。

### 13.7 Memory 要求

Memory 是降低 token 消耗和提升个性化/环境认知的关键能力，需要保留并增强。

分层：
- User memory：用户偏好、常用语言、报告格式。
- Lab memory：Storage/GPU/K8S 拓扑、命名规则、常见故障、维护窗口。
- Target memory：每台服务器/集群的硬件、服务、历史异常、基线指标。
- Agent memory：每个 Agent 的已知限制、常用流程、上次任务状态。

约束：
- Memory 注入必须 cache-aware，不能在一个长 session 中频繁改写系统提示。
- 大块历史通过 summary + retrieval 注入，不把完整历史塞进 prompt。
- 敏感信息不进长期 memory；密钥、token、私网凭据只存在配置/secret。

### 13.8 Token Usage Tracking

Hermes 已经具备 token usage 相关能力：
- `agent/usage_pricing.py` 定义了 usage 归一化、价格表、成本估算。
- `agent/transports/chat_completions.py`、`agent/transports/anthropic.py`、`agent/transports/codex.py` 等会从 provider response 中读取 `usage` 字段。
- 当前 ProAgent 独立 loop 需要把这些 usage 信息显式捕获并持久化，否则 GUI/Discord 无法展示 agent 级成本。

ProAgent 需要新增：
- `UsageRecord(session_id, agent_id, provider, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, estimated_cost, created_at)`。
- 每次 LLM call 后写入 `usage.db`，并把 session total 写入 session summary。
- Web UI 展示 per-agent / per-session / daily token usage。
- Discord `/agent usage [today|session]` 查询当前消耗。
- 阈值告警：超过 daily budget 时向 Discord 提醒，必要时切换 cheaper model 或要求用户确认继续。

### 13.9 文档与 Phase Hook

本项目按 PRD / requirement 驱动开发。以下变更必须先更新文档再改代码：
- 新 Agent、Agent 职责变化、slash command 变化。
- feature 级代码变更或架构设计变化。
- 进入下一 phase 或调整 phase 里程碑。
- Hermes 代码归档/裁剪策略变化。
- Memory、Skill、Token usage、权限模型的行为变化。

必须更新：
- `docs/ProAgent-Redesign-Plan.md`：长期产品设计和跨 phase 决策。
- 当前 phase doc（例如 `docs/ProAgent-Phase5-Plan.md`）：本 phase 的任务、验收标准和进展。
- `AGENTS.md`：当 coding instruction、测试命令、目录结构、文档 hook 或安全规则发生变化。

### 13.10 Phase 5 里程碑

| # | 里程碑 | 交付物 | 状态 |
| --- | --- | --- | --- |
| M5.1 | Develop Agent Domain Pack | `proagent/domain/develop_agent/` pack.yaml / prompt / policy / skills | 待实现 |
| M5.2 | Requirement Work Item Store | PRD/feature/bugfix work item schema + CLI/API | 待实现 |
| M5.3 | Discord Agent Router | `/aigc` `/test` `/develop` `/sre` slash routing + channel default Agent | 待实现 |
| M5.4 | 7x24 Gateway Hardening | reconnect / heartbeat / healthcheck / Docker deployment | 待实现 |
| M5.5 | Web UI Session History | SRE/Test/Develop session history + filters + detail view | 待实现 |
| M5.6 | Develop Board | feature/bugfix status, linked docs, changed files, test status | 待实现 |
| M5.7 | Test Dashboard | requirement coverage matrix + test case status + latest run evidence | 待实现 |
| M5.8 | Skill Draft Generator | automatic skill draft + approval workflow + dry-run tests | 待实现 |
| M5.9 | Memory Upgrade | layered user/lab/target/agent memory + retrieval summaries | 待实现 |
| M5.10 | Token Usage Tracking | usage capture, usage.db, Web UI and Discord usage commands | 待实现 |
| M5.11 | Hermes Archive Pass | move/disable useless code with import/test validation | 待实现 |
| M5.12 | E2E Validation | Test Agent validates SRE/AIGC/Develop + Discord/Web UI flows | 待实现 |

### 13.10.1 Phase 5 Baseline Progress (2026-05-20)

已完成可部署产品化骨架：

- 新增 `develop-agent` Domain Pack，包含 prompt、policy、knowledge、requirement/feature/bugfix/docs sync skills。
- 新增 `proagent.storage.phase5`：`session_history.db`、`work_items.db`、`usage.db` 的 SQLite store。
- 新增 `proagent.core.agent_router.AgentRouter`，支持 `/sre`、`/test`、`/develop`、`/aigc` 和 `/agent switch/status/usage`。
- `proagent gateway` 接入 router、session history，并提供 `/health` HTTP endpoint 供 Docker healthcheck 使用。
- Streamlit Web UI 增加 Session History、Develop Board、Test Dashboard、Token Usage 面板。
- 新增 `Dockerfile.proagent`、`docker-compose.proagent.yml`、`.env.proagent.example`，用于 ProAgent gateway + web 双服务部署。

剩余关键缺口：

- 企业级自动审批流、真实 Discord 线上 7x24 soak test、以及物理移动大型 Hermes 目录仍需后续运维窗口执行。
- Phase 5 baseline 已具备 `UsageStore` provider usage hook、`SkillDraftStore` draft→enable、`LayeredMemoryStore`、Develop work item tools、Web UI 检查面板和 `docs/Hermes-Archive-Plan.md`。
- Memory baseline 已升级为 user-scoped：同一套 Agent Loop 会按 gateway/user identity 检索并注入当前用户的个人记忆，`memory_remember` / `memory_search` 内置工具用于沉淀和读取客户偏好、反复出现的需求、验收偏好等信息；不同 user_id 的 user-layer memory 不互相注入。

### 13.11 Phase 5 DoD

1. Discord can run 7x24 in Docker and route `/aigc`, `/test`, `/develop`, `/sre` to isolated Agent sessions.
2. Develop Agent can take a requirement/bugfix, update docs, implement code, and hand off to Test Agent.
3. Test Agent can run the relevant unit/real tests and show requirement coverage plus status in Web UI.
4. SRE Agent session history for troubleshooting/check status is searchable in Web UI.
5. Web UI shows Develop work items, test cases/status, and token usage per Agent/session.
6. AIGC Agent remains isolated from SRE/Test/Develop toolsets and is usable from Discord.
7. At least one auto-created skill goes through draft → review → enable → dry-run validation.
8. Token usage is persisted for every LLM call and visible through Web UI and Discord.
9. Hermes archive pass removes or disables unused code without breaking domain load, policy guard, Discord gateway import, or GUI import.
