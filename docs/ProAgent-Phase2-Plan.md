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

### 2.2 存储监控（Ceph + JuiceFS）

**目标**：通过 Prometheus metrics 端点获取 Ceph/JuiceFS 状态，Agent 定期巡检 + 异常时 Discord 汇报并询问是否深入分析。

#### 2.2.1 监控数据源

| 组件 | Metrics 端点 | 部署位置 | 关键指标 |
|------|-------------|---------|---------|
| Node Exporter (含 Ceph) | `http://10.11.4.20:9100/metrics` | Ceph/存储节点 | 磁盘IO/网络/CPU + Ceph 相关 |
| JuiceFS | `http://localhost:9567/metrics` | 各客户端节点 | 读写延迟/缓存命中/元数据操作 |

#### 2.2.2 工作流程

```
定时巡检 / 用户提问
        │
        ▼
┌─────────────────────────────┐
│  Metrics Fetcher (read_only)│
│  curl → parse Prometheus    │
│  text format → 结构化数据   │
└───────────┬─────────────────┘
            ▼
┌─────────────────────────────┐
│  Agent 分析                 │
│  - 对比阈值                 │
│  - 识别异常模式             │
│  - 生成状态摘要             │
└───────────┬─────────────────┘
            ▼
        正常？──Yes──→ 记录，不打扰
            │
           No
            ▼
┌─────────────────────────────┐
│  Discord 汇报               │
│  "发现 Ceph OSD.3 down，    │
│   是否需要进一步分析？"      │
│  [详细分析] [忽略]           │
└───────────┬─────────────────┘
            ▼ 用户点击"详细分析"
┌─────────────────────────────┐
│  深度诊断（只读）            │
│  - ceph status              │
│  - ceph osd tree            │
│  - ceph health detail       │
│  - 相关 node metrics        │
│  → 给出根因假设 + 建议方案  │
│  → 不执行任何修复操作        │
└─────────────────────────────┘
```

#### 2.2.3 Ceph 关键指标与阈值

| 指标 | Prometheus metric | 注意阈值 | 异常阈值 |
|------|------------------|---------|---------|
| 集群健康 | `ceph_health_status` | ≠ 0 (WARN) | = 2 (ERR) |
| OSD 状态 | `ceph_osd_up`, `ceph_osd_in` | any down | >1 down |
| PG 状态 | `ceph_pg_degraded`, `ceph_pg_undersized` | > 0 | 持续 > 5min |
| 容量 | `ceph_cluster_total_used_bytes / total_bytes` | > 75% | > 85% |
| IOPS | `ceph_osd_op_r`, `ceph_osd_op_w` | 突增 2x | 突增 5x |
| 延迟 | `ceph_osd_apply_latency_ms` | > 20ms | > 100ms |

#### 2.2.4 JuiceFS 关键指标与阈值

| 指标 | Prometheus metric | 注意阈值 | 异常阈值 |
|------|------------------|---------|---------|
| 读延迟 | `juicefs_object_request_durations_histogram_seconds` | P99 > 100ms | P99 > 500ms |
| 写延迟 | 同上 (method=put) | P99 > 200ms | P99 > 1s |
| 缓存命中率 | `juicefs_blockcache_hits / (hits+miss)` | < 80% | < 50% |
| 元数据操作 | `juicefs_transaction_durations_histogram_seconds` | P99 > 50ms | P99 > 200ms |
| 使用空间 | `juicefs_used_space` | 接近 quota | 超过 quota |

#### 2.2.5 实现方式

Agent 通过 `server_shell` 工具执行 `curl` 获取 metrics，然后由 LLM 解析 Prometheus text format：

```bash
# Node Exporter（存储节点，含磁盘/网络/CPU）
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_(disk_io|filesystem_avail|network)' | head -50")

# JuiceFS metrics（客户端节点）
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_(object_request|blockcache|transaction|used)' | head -50")
```

**注意**：所有操作均为只读（curl GET），不执行任何 ceph/juicefs 写命令。

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
│  │  [Phase 2] Storage Monitor (Ceph + JuiceFS)                  │    │
│  │  - curl Prometheus metrics (read-only GET)                   │    │
│  │  - Ceph: :9283 + :9100 | JuiceFS: :9567                     │    │
│  │  - 阈值判定 → Discord 汇报 → 询问深入分析                   │    │
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
│   │   ├── ontology.py              # ✅ Topology loader (topology.yaml → system prompt)
│   │   ├── alert_router.py         # [待实现] 告警路由
│   │   ├── metrics_fetcher.py      # [待实现] Prometheus metrics 抓取与解析
│   │   └── target_import.py        # ✅ 批量导入 hosts.yaml (range expansion)
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

| # | 里程碑 | 交付物 | 状态 |
|---|--------|--------|------|
| M2.1 | 多主机批量导入 | `target import hosts.yaml` + range 语法 | ✅ 完成 |
| M2.2 | Kubeconfig 接入 | kubectl read 允许 / write 拦截 + kubeconfig 占位 | ✅ 完成 |
| M2.3 | Ontology Framework | topology.yaml + ontology.py 加载器 + 注入 system prompt | ✅ 完成 |
| M2.4 | Target Group | 按 role/tag 筛选 + 并行执行 | 待实现 |
| M2.5 | 连接池优化 | 并行连接 + 健康检查 + 自动重连 | 待实现 |
| M2.6 | Ceph Metrics 巡检 | curl 9100 → 解析 → 阈值判定 → 报告 | 待实现 |
| M2.7 | JuiceFS Metrics 巡检 | curl 9567 → 解析 → 阈值判定 → 报告 | 待实现 |
| M2.8 | 存储异常 Discord 汇报 | 发现问题 → 推送 → 询问是否深入 → 深度诊断 | 待实现 |
| M2.9 | Skill 模式检测 | 识别重复命令序列 | 待实现 |
| M2.10 | Skill 草稿生成 | 命令序列 → SKILL.md 模板 | 待实现 |
| M2.11 | Skill 人工审核流 | Discord/Feishu 按钮 approve/reject | 待实现 |
| M2.12 | 定时巡检推送 | Cron → 巡检(主机+存储) → Discord/Feishu 推送 | 待实现 |
| M2.13 | Session 持久化 | 对话历史跨重启保留 | 待实现 |
| M2.14 | 文档更新 | 部署指南 + 存储监控指南 + Skill 开发指南 | 进行中 |

---

## 5. Phase 2 验收标准

1. `python proagent_run.py target import hosts.yaml` 一次导入 20 台服务器
2. `python proagent_run.py target test --all` 并行测试所有目标（< 30s）
3. Agent 能通过 curl 获取 Ceph metrics 并正确判断集群健康状态
4. Agent 能通过 curl 获取 JuiceFS metrics 并分析读写延迟
5. 发现存储异常时自动推送到 Discord，用户确认后给出深度分析（只读）
6. Agent 对同类问题诊断 3 次后，自动提议新 Skill
7. 用户在 Discord 点击 ✅ 后，新 Skill 立即生效
8. 定时巡检（主机 + 存储）每小时推送到 Discord，格式结构化
9. 连续运行 7 天无 SSH 连接泄漏
10. **全程无任何写操作**（不执行 ceph osd repair / juicefs gc 等）

---

## 6. 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 存储监控方式 | curl Prometheus metrics endpoint | 纯只读 GET，无需额外 agent，复用现有 exporter |
| Metrics 解析 | LLM 直接解析 Prometheus text format | 灵活，无需写 parser；Agent 可自行 grep 关键指标 |
| 异常通知 | Discord 推送 + 询问是否深入 | 避免信息轰炸，用户决定是否深入 |
| 并行执行 | ThreadPoolExecutor(10) | SSH 是 IO 密集，线程足够 |
| Skill 存储 | 文件系统 (skills/*.md) | 可 git 管理、可 review、可回滚 |
| 审核流 | Discord 按钮 / Feishu 卡片 | 用户已在这些平台，无需新 UI |
| 定时任务 | OS cron 调用 proagent inspect | 最简单可靠，不引入新调度器 |
| Session 持久化 | SQLite (messages 表) | 复用 audit.db 同一数据库 |
| 写操作 | **全面禁止** | Phase 2 仍为只读；不执行 ceph repair / juicefs gc 等 |

---

## 7. 风险

| 风险 | 缓解 |
|------|------|
| 20 台并行 SSH 连接不稳定 | 连接池 + 指数退避重连 + 健康检查 |
| Metrics endpoint 不可达 | curl 超时 5s + 标记为 unreachable + 不阻塞其他巡检 |
| Prometheus text format 解析不准 | 用 grep 预过滤关键行，减少 LLM 输入噪音 |
| Skill 自动生成质量差 | 必须人工审核；生成时引用 evidence |
| Discord 代理不稳定 | 支持 Feishu 作为备用通道 |
| Agent 误判存储异常 | 阈值保守设置；异常只汇报不执行 |

---

**文档状态**: Draft v0.2 · 基于 Phase 1 实际运行经验制定

---

## Phase 3 进展记录（2026-05-12）

| 里程碑 | 状态 |
|--------|------|
| MiniMax CLI 安装 | ✅ `pip install minimax-cli` (mmx 命令) |
| AIGC Domain Pack | ✅ `proagent/domain/aigc_creator/` |
| Domain Switch CLI | ✅ `proagent domain list` / `proagent domain use <id>` |
| 图片生成验证 | ✅ 熊猫动漫风格图片生成成功 |
| Domain 隔离 | ✅ SRE 模式无 AIGC 工具，AIGC 模式无 SSH 工具 |
| Phase 3 Requirements Spec | ✅ `.kiro/specs/phase3-security-domain-packs/requirements.md` |
| Test Agent Pack | ✅ `proagent/domain/test_agent/` |
| AIGC Image Gen Test Cases | ✅ `proagent/domain/test_agent/tests/test_aigc_image_generation.py` |
| Local-only Domain Run Mode | ✅ `proagent run` 自动跳过 SSH 连接（test-agent / aigc-creator） |
| SRE Server Shell Test Cases | ✅ `proagent/domain/test_agent/tests/test_sre_server_shell.py` |
| Environment Variable Loading | ✅ `.env` file loading via python-dotenv |
| Configurable max_iterations | ✅ Per-domain pack via `max_iterations` in pack.yaml |

待实现：LLM 审计 (R1)、安全护栏 (R2)、回滚接口 (R3)、执行后端抽象 (R6)

---

## Phase 4 进展记录（2026-05-12）

**目标**：完成三 Agent 产品化能力闭环 + 统一 GUI 入口。所有里程碑均已交付并通过 Test Agent 验证。

### 三 Agent 闭环

| 里程碑 | 交付物 | 状态 |
|--------|--------|------|
| M4.1 SRE 写操作白名单 | `write_diagnosis_report` + `write_inspection_report` + Policy `write_action_whitelist` | ✅ |
| M4.2 SRE 自动诊断 SOP | `system_prompt.md` 注入故障排查 + 定期巡检流程 | ✅ |
| M4.3 SRE 报告生成 | 输出至 `proagent/storage/reports/diagnosis-*.md` 和 `inspection-*.md` | ✅ |
| M4.4 AIGC 提示词优化 | `prompt_optimize` 工具 + 10 种风格预设 + 质量增强器 | ✅ |
| M4.5 AIGC 多图生成 | `image_generate_batch` 单次最多 8 张，每张独立 seed | ✅ |
| M4.6 AIGC 历史 + 反馈 | SQLite (`aigc_history.db`) + `image_history_list` + `image_feedback` | ✅ |
| M4.7 Test 代码扫描 | `code_scan` 递归识别可测试单元，跳过 vendor 目录 | ✅ |
| M4.8 Test PRD 解析 | `prd_parse` 提取 EARS / 用户故事 / Bullet 功能 | ✅ |
| M4.9 Test 报告输出 | `report_generate` Markdown/HTML 报告 | ✅ |

### 统一 GUI

| 里程碑 | 交付物 | 状态 |
|--------|--------|------|
| M4.10 GUI 后端 | 复用 ProAgent runtime + ProAgent agent 直接调用（无单独 API Server） | ✅ |
| M4.11 Streamlit GUI | `proagent/gui/app.py` 四面板：对话/报告库/图片画廊/状态 | ✅ |
| M4.12 E2E 验证 | Test Agent `pytest` 110 passed, 2 skipped, 0 failed | ✅ |
| M4.13 文档更新 | Phase 2 Plan + Redesign Plan + 命令示例 | ✅ |

### 安全模型升级

| 维度 | Phase 3 | Phase 4 |
|------|---------|---------|
| write_action 默认 | 全 DENY | 全 DENY，但支持 per-domain 白名单 |
| 工具 category | 隐式 | 显式（`ToolDef.category`） |
| Policy Guard 调用点 | 仅 shell denylist | shell denylist + 工具 category check |
| 配置位置 | pack.yaml `capabilities` | + policy.yaml `write_action_whitelist` |

SRE 仅允许两个写工具，AIGC 允许 `aigc_generate / image_generate_batch / image_feedback`，Test Agent 仅允许 `report_generate`。所有非白名单 write_action 一律 `Decision.DENY`。

### 入口示例

```bash
# CLI（按 domain 切换）
python proagent_run.py domain use server-health-inspector && python proagent_run.py run -v
python proagent_run.py domain use aigc-creator && python proagent_run.py run -v
python proagent_run.py domain use test-agent && python proagent_run.py run -v

# 统一 GUI（推荐）
python proagent_run.py gui   # 默认 http://localhost:8501
```

### 与"真正产品"的剩余差距（Phase 5+ 路线）

- 多用户 Auth / RBAC
- Session 持久化（重启后历史保留）
- Discord 审批按钮（当前 GUI 无审批流，仅本地策略）
- Prometheus metrics + OpenTelemetry trace
- Docker / docker-compose 部署清单
- Provider fallback（多 provider 容错）
- PII 脱敏 + 密钥轮换
- Cron 定时巡检 + Discord 推送（框架已就绪，仅需配置）
