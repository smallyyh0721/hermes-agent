# ProAgent Phase 2 计划：多主机 + 告警接入 + Skill 自动生成

> 版本: v0.2
> 前置: Phase 1 已完成（单机巡检 + Discord/CLI Chat + Policy Guard + 审计）
> 目标: 从"单机验证"走向"多机生产可用"

---

## 1. Phase 1 完成状态确认

### 1.1 已交付能力

| 能力 | 状态 | 验证方式 |
|------|------|---------|
| CLI 交互式 Chat | ✅ | `python proagent_run.py run -v` |
| Discord Gateway | ✅ | `python proagent_run.py gateway`（需代理） |
| SSH 连接目标服务器 | ✅ | `python proagent_run.py target test` |
| Policy Guard (denylist) | ✅ | 57 条规则，写操作硬拦截 |
| 审计日志 (SQLite) | ✅ | `proagent/storage/audit.db` |
| 模型支持 (MiniMax CN/OpenAI/Anthropic) | ✅ | `python proagent_run.py model test` |
| Verbose 追踪 | ✅ | `-v` 显示工具调用链 |
| 一次性巡检 | ✅ | `python proagent_run.py inspect --kind quick` |
| 代码精简 | ✅ | 删除 66 文件 / 57k LOC |
| Windows SSH 兼容 | ✅ | 跳过 ControlMaster |

### 1.2 已知限制（Phase 2 解决）

| 限制 | 影响 | Phase 2 方案 |
|------|------|-------------|
| 单台服务器配置繁琐 | 多台时需反复 setup | 批量导入 + 自动发现 |
| 无告警接入 | 被动等用户提问 | Webhook 接入 Alertmanager/Zabbix |
| Skill 手动编写 | 新场景需开发者介入 | Agent 自动生成 + 人工审核 |
| 无定时推送 | 巡检结果只在 CLI 看 | Cron → Discord/Feishu 推送 |
| 单 session 无持久化 | 重启丢上下文 | Session 持久化 |

---

## 2. Phase 2 范围

### 2.1 多主机快速配置

**目标**：5 分钟内接入 20 台服务器。

#### 2.1.1 批量导入

```yaml
# hosts.yaml - 批量导入格式
hosts:
  - id: web-01
    host: 10.11.4.13
    user: ops
    role: web
    tags: [production, frontend]

  - id: web-02
    host: 10.11.4.14
    user: ops
    role: web
    tags: [production, frontend]

  - id: db-01
    host: 10.11.4.20
    user: dba
    role: database
    tags: [production, mysql]

  # 支持 range 语法
  - id: worker-{01..10}
    host: 10.11.5.{1..10}
    user: ops
    role: worker
    tags: [production, compute]

defaults:
  port: 22
  keyfile: ~/.ssh/id_ed25519
  backend: ssh
```

CLI 命令：

```bash
# 批量导入
python proagent_run.py target import hosts.yaml

# 批量测试
python proagent_run.py target test --all

# 按 tag 筛选
python proagent_run.py target list --tag production
python proagent_run.py target test --tag database

# 自动发现（扫描网段）
python proagent_run.py target discover --subnet 10.11.4.0/24 --user ops
```

#### 2.1.2 Target Group（目标组）

```yaml
# proagent.yaml 新增
target_groups:
  all-web:
    filter: { role: web }
  all-prod:
    filter: { tags: [production] }
  databases:
    filter: { role: database }
```

Chat 中使用：
```
🧑 > 检查所有 web 服务器的磁盘
Agent: 正在检查 web-01, web-02...（并行执行）
```

#### 2.1.3 连接池优化

- 并行连接（ThreadPoolExecutor，max_workers=10）
- 连接健康检查定时器（每 5 分钟）
- 失败自动重连（指数退避）
- 连接状态 Dashboard（`proagent status --targets`）

---

### 2.2 告警接入

**目标**：外部监控系统推送告警 → Agent 自动诊断 → 推送结果到 Discord/Feishu。

#### 2.2.1 Webhook 接口

```
POST /webhook/alert
Content-Type: application/json

{
  "source": "alertmanager",     // alertmanager | zabbix | prometheus | custom
  "severity": "warning",        // critical | warning | info
  "target": "web-01",           // 匹配 proagent.yaml 中的 target id
  "metric": "disk_usage",       // 触发指标
  "value": "92%",               // 当前值
  "threshold": "90%",           // 阈值
  "message": "/data 分区使用率超过 90%",
  "labels": {
    "instance": "10.11.4.13:9100",
    "mountpoint": "/data"
  }
}
```

#### 2.2.2 告警处理流程

```
Alertmanager/Zabbix/Prometheus
        │
        ▼ POST /webhook/alert
┌─────────────────────────────┐
│  Alert Router               │
│  - 解析 source 格式         │
│  - 匹配 target              │
│  - 确定 severity → skill    │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  ProAgent Runtime           │
│  - 选择对应 diagnose skill  │
│  - 执行 read_only 命令      │
│  - 生成诊断报告             │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  Delivery                   │
│  - Discord channel 推送     │
│  - Feishu 群消息            │
│  - 存入 incident_history    │
│  - 更新 audit_event         │
└─────────────────────────────┘
```

#### 2.2.3 Alertmanager 适配

```yaml
# alertmanager.yml 配置示例
receivers:
  - name: proagent
    webhook_configs:
      - url: http://proagent-host:8787/webhook/alert
        send_resolved: true

route:
  receiver: proagent
  group_by: [alertname, instance]
  group_wait: 30s
```

#### 2.2.4 告警去重与抑制

- 同一 target + metric 在 5 分钟内不重复诊断
- severity=info 只记录不诊断
- severity=critical 立即诊断 + 推送
- resolved 事件关闭 incident

---

### 2.3 Skill 自动生成

**目标**：Agent 在诊断过程中发现新模式 → 自动提议新 Skill → 人工审核后合并。

#### 2.3.1 触发条件

- Agent 连续 3 次对同类问题使用相似的命令序列
- 用户明确说"把这个流程保存为 skill"
- 巡检发现新类型异常，现有 skill 未覆盖

#### 2.3.2 生成流程

```
Agent 诊断完成
    │
    ▼ 检测到可复用模式
┌─────────────────────────────┐
│  Skill Generator            │
│  - 提取命令序列             │
│  - 归纳 When/Stop/Output    │
│  - 生成 SKILL.md 草稿       │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  Human Review               │
│  - 推送到 Discord/Feishu    │
│  - 用户 approve / reject    │
│  - approve → 写入 skills/   │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  Skill Registry             │
│  - 加载新 skill             │
│  - 下次同类问题自动使用     │
└─────────────────────────────┘
```

#### 2.3.3 生成的 Skill 格式

```markdown
# GPU Temperature Monitor (auto-generated)

## When to use
- 用户询问 GPU 温度
- 告警包含 gpu_temperature 指标
- 巡检发现 nvidia-smi 可用

## Inputs required
- target: 目标服务器

## Procedure
1. server_shell(command="nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader")
2. server_shell(command="nvidia-smi --query-gpu=power.draw,power.limit --format=csv,noheader")

## Tools allowed
- server_shell (read_only)

## Stop conditions
- nvidia-smi 不可用时跳过

## Output format
GPU 状态报告：型号、温度、利用率、显存、功耗

## Generated from
- session: abc123
- date: 2026-05-11
- trigger: user asked "GPU 温度多少"
```

---

## 3. 软件架构图（当前 + Phase 2 规划）

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Inbound Layer                                │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Discord  │  Feishu  │   CLI    │ REST API │ Webhook  │    Cron     │
│ (proxy)  │          │  (REPL)  │ :8787    │ /alert   │ (OS cron)   │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────┬──────┘
     │          │          │          │          │            │
     └──────────┴──────────┴──────┬───┴──────────┴────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ProAgent Core Runtime                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Agent Loop   │  │ Config Loader│  │ Provider Registry        │  │
│  │ (agent.py)   │  │ (config.py)  │  │ (providers.py)           │  │
│  │              │  │              │  │ minimax-cn/openai/claude  │  │
│  │ LLM ←→ Tool │  │ proagent.yaml│  └──────────────────────────┘  │
│  │   ↕          │  └──────────────┘                                 │
│  │ Messages     │  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ History      │  │ SSH Pool     │  │ Alert Router [Phase 2]   │  │
│  └──────────────┘  │ (ssh_pool.py)│  │ (alert_router.py)        │  │
│                     │ ControlMaster│  └──────────────────────────┘  │
│                     │ + Reconnect  │                                 │
│                     └──────────────┘                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Domain Pack Layer                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  server_health_inspector/                                    │    │
│  │  ├── system_prompt.md    (领域人格 + 规则)                   │    │
│  │  ├── knowledge/          (阈值/术语/诊断路径)                │    │
│  │  ├── skills/             (SOP: quick_check / full / diagnose)│    │
│  │  ├── tools/read_only/    (server_shell)                      │    │
│  │  └── policy.yaml         (57 条 denylist 规则)               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  [Phase 2] Skill Generator                                   │    │
│  │  - 模式检测 → 草稿生成 → 人工审核 → 注册                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Policy Guard                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Denylist     │  │ Audit Store  │  │ Rate Limiter [Phase 2]   │  │
│  │ (guard.py)   │  │ (audit.py)   │  │                          │  │
│  │ 57 patterns  │  │ SQLite       │  │ per-user / per-target    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Execution Layer                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Local   │  │   SSH    │  │  Docker  │  │ [Phase 3] K8s     │  │
│  │  shell   │  │  remote  │  │  exec    │  │  exec             │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Outbound / Delivery                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Discord  │  │  Feishu  │  │  CLI     │  │ incident_history  │  │
│  │ reply    │  │  msg/doc │  │  stdout  │  │ (knowledge/)      │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 代码目录结构与说明

```
hermes-agent/
├── proagent_run.py                 # 🚀 主入口脚本
├── proagent.yaml                   # ⚙️ 运行时配置（用户生成，不入库）
├── proagent.yaml.example           # 📄 配置模板
│
├── proagent/                       # ═══ ProAgent 核心代码 ═══
│   ├── __init__.py                 # 版本号
│   ├── README.md                   # 快速上手指南
│   │
│   ├── core/                       # ── 核心运行时 ──
│   │   ├── agent.py                # 最小 Agent 循环（OpenAI/Anthropic function calling）
│   │   ├── config.py               # proagent.yaml 加载/保存
│   │   ├── providers.py            # LLM Provider 注册表（minimax-cn/openai/anthropic）
│   │   ├── runtime.py              # 编排器：Config + SSH + Policy + Domain → Agent
│   │   ├── ssh_pool.py             # SSH 连接池（ControlMaster/Windows 兼容/重连）
│   │   ├── alert_router.py         # [Phase 2] 告警路由：解析 → 匹配 target → 触发 skill
│   │   └── target_import.py        # [Phase 2] 批量导入 hosts.yaml / 网段扫描
│   │
│   ├── policy/                     # ── 安全与审计 ──
│   │   ├── guard.py                # Policy Guard：denylist 正则匹配 + 决策
│   │   ├── audit.py                # SQLite 审计存储（audit_event + inspection_run）
│   │   └── rate_limiter.py         # [Phase 2] 频率限制（per-user / per-target）
│   │
│   ├── domain/                     # ── 领域包 ──
│   │   ├── __init__.py
│   │   └── server_health_inspector/
│   │       ├── pack.yaml           # 包元数据（版本/模型/能力声明）
│   │       ├── system_prompt.md    # 领域系统提示词（角色 + 规则 + 输出格式）
│   │       ├── policy.yaml         # 57 条 denylist 规则
│   │       ├── knowledge/
│   │       │   └── index.md        # 诊断知识索引（阈值/路径/术语）
│   │       ├── skills/
│   │       │   ├── quick_health_check.md      # 快速巡检 SOP
│   │       │   └── full_health_inspection.md  # 深度巡检 SOP
│   │       ├── tools/
│   │       │   ├── read_only/
│   │       │   │   └── server_shell.py        # 核心工具：SSH 执行只读命令
│   │       │   └── suggest/                   # [Phase 2] 建议类工具
│   │       └── tests/                         # 领域回归测试
│   │
│   ├── skill_gen/                  # [Phase 2] ── Skill 自动生成 ──
│   │   ├── detector.py             # 模式检测：识别可复用命令序列
│   │   ├── generator.py            # 草稿生成：命令序列 → SKILL.md
│   │   └── reviewer.py             # 人工审核流：推送 → approve/reject → 注册
│   │
│   ├── gateway_profile/
│   │   └── phase1.yaml             # 启用/禁用的 Gateway 列表
│   │
│   ├── cli/
│   │   └── main.py                 # CLI 命令分发（run/setup/model/target/inspect/gateway）
│   │
│   ├── storage/
│   │   ├── .gitkeep
│   │   └── audit.db                # 运行时审计数据库（不入库）
│   │
│   └── tests/
│       ├── test_basic.py           # 核心集成测试（5 项）
│       └── test_redirect.py        # Policy 重定向规则测试
│
├── docs/                           # ═══ 文档 ═══
│   ├── RedesignHermes.md           # 初始改造思路
│   ├── ProAgent-Redesign-Plan.md   # Phase 1 完整 SPEC
│   ├── ProAgent-Phase2-Plan.md     # Phase 2 计划（本文档）
│   └── ProAgent-Manual-Test.md     # 人工测试指南
│
└── (Hermes 原始代码保留，ProAgent 不依赖其入口)
    ├── agent/                      # Hermes Agent 核心（保留参考）
    ├── gateway/platforms/          # 保留: discord/weixin/feishu/api_server/webhook
    ├── tools/                      # 保留: registry/terminal/file/skills 等基础
    ├── cron/                       # 保留: 定时任务基础设施
    └── ...
```

---

## 4. Phase 2 里程碑

| # | 里程碑 | 交付物 | 预估工期 |
|---|--------|--------|---------|
| M2.1 | 多主机批量导入 | `target import hosts.yaml` + range 语法 + `--all` 测试 | 2 天 |
| M2.2 | Target Group | 按 role/tag 筛选 + 并行执行 | 2 天 |
| M2.3 | 连接池优化 | 并行连接 + 健康检查 + 自动重连 | 2 天 |
| M2.4 | Webhook 告警接口 | `POST /webhook/alert` + Alertmanager 适配 | 3 天 |
| M2.5 | 告警路由 + 自动诊断 | severity → skill 映射 + 去重 | 2 天 |
| M2.6 | 诊断结果推送 | Discord/Feishu 自动推送 + incident_history | 2 天 |
| M2.7 | Skill 模式检测 | 识别重复命令序列 | 3 天 |
| M2.8 | Skill 草稿生成 | 命令序列 → SKILL.md 模板 | 2 天 |
| M2.9 | Skill 人工审核流 | Discord/Feishu 按钮 approve/reject | 2 天 |
| M2.10 | 定时巡检推送 | Cron → 巡检 → Discord/Feishu 推送 | 2 天 |
| M2.11 | Session 持久化 | 对话历史跨重启保留 | 1 天 |
| M2.12 | 文档更新 | 部署指南 + 告警接入指南 + Skill 开发指南 | 2 天 |

**总预估**: ~25 天（可并行，实际 2-3 周）

---

## 5. Phase 2 验收标准

1. `python proagent_run.py target import hosts.yaml` 一次导入 20 台服务器
2. `python proagent_run.py target test --all` 并行测试所有目标（< 30s）
3. Alertmanager 发送告警 → 5s 内 Agent 开始诊断 → 30s 内推送结果到 Discord
4. Agent 对同类问题诊断 3 次后，自动提议新 Skill
5. 用户在 Discord 点击 ✅ 后，新 Skill 立即生效
6. 定时巡检每小时推送到 Discord，格式结构化
7. 连续运行 7 天无 SSH 连接泄漏

---

## 6. 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 告警接口格式 | 兼容 Alertmanager webhook | 最广泛使用的开源告警系统 |
| 并行执行 | ThreadPoolExecutor(10) | SSH 是 IO 密集，线程足够 |
| Skill 存储 | 文件系统 (skills/*.md) | 可 git 管理、可 review、可回滚 |
| 审核流 | Discord 按钮 / Feishu 卡片 | 用户已在这些平台，无需新 UI |
| 定时任务 | OS cron 调用 proagent inspect | 最简单可靠，不引入新调度器 |
| Session 持久化 | SQLite (messages 表) | 复用 audit.db 同一数据库 |

---

## 7. 风险

| 风险 | 缓解 |
|------|------|
| 20 台并行 SSH 连接不稳定 | 连接池 + 指数退避重连 + 健康检查 |
| 告警风暴（短时间大量告警） | 去重窗口 5min + 批量合并 + 限流 |
| Skill 自动生成质量差 | 必须人工审核；生成时引用 evidence |
| Discord 代理不稳定 | 支持 Feishu 作为备用通道 |

---

**文档状态**: Draft v0.2 · 基于 Phase 1 实际运行经验制定
