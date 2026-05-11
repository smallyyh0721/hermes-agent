# ProAgent - Professional Domain Agent Runtime

基于 Hermes Agent 构建的专业领域 Agent Runtime。

## 快速开始

### 1. 配置

```bash
# 交互式配置
python proagent_run.py setup

# 或复制示例配置
cp proagent.yaml.example proagent.yaml
# 编辑 proagent.yaml 填入你的配置
```

### 2. 配置模型

确保设置了 API Key 环境变量：
```bash
export OPENAI_API_KEY="sk-..."
# 或
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. 配置目标服务器

编辑 `proagent.yaml` 中的 `targets` 部分，或使用 CLI：
```bash
python proagent_run.py target add --id web-01 --backend ssh --host 10.0.0.11 --user ops --keyfile ~/.ssh/id_ed25519
python proagent_run.py target test web-01
```

### 4. 启动

```bash
# 交互式 Chat（CLI 模式）
python proagent_run.py run

# 指定目标
python proagent_run.py run --target web-01

# 一次性巡检
python proagent_run.py inspect --kind full --target web-01

# 启动 Discord Gateway
python proagent_run.py gateway
```

## 测试

```bash
python proagent/tests/test_basic.py
```

## 目录结构

```
proagent/
├── core/
│   ├── runtime.py      # 核心运行时（编排 Agent + Domain + Policy）
│   ├── config.py       # 配置加载（proagent.yaml）
│   └── ssh_pool.py     # SSH 连接池（ControlMaster + 健康检查）
├── policy/
│   ├── guard.py        # Policy Guard（denylist 命令拦截）
│   └── audit.py        # 审计存储（SQLite）
├── domain/
│   └── server_health_inspector/
│       ├── pack.yaml           # Domain Pack 元数据
│       ├── system_prompt.md    # 领域系统提示词
│       ├── policy.yaml         # 权限策略（57 条 denylist 规则）
│       ├── knowledge/          # 领域知识库
│       ├── skills/             # SOP 技能模板
│       └── tools/read_only/    # 只读工具（server_shell）
├── cli/
│   └── main.py         # CLI 入口（run/setup/model/target/inspect/gateway）
├── gateway_profile/
│   └── phase1.yaml     # Phase 1 启用的 Gateway 列表
├── storage/            # 运行时数据（audit.db）
└── tests/
    └── test_basic.py   # 集成测试
```

## Phase 1 测试流程

1. **配置 Discord 连接** → `proagent.yaml` 中设置 Discord token
2. **配置模型** → 设置 OPENAI_API_KEY，运行 `proagent model test`
3. **Chat 交互** → `proagent run`，问 "服务器状态如何？"
4. **配置巡检** → 设置 cron jobs，定时出报告
5. **故障注入** → 手动制造问题（如填满磁盘），验证 Agent 诊断能力

## 安全保证

- 所有 shell 命令经过 57 条 denylist 正则匹配
- 写操作（rm/kill/systemctl restart/reboot/...）被硬拦截
- 每次工具调用记录审计日志
- SSH 使用 ControlMaster + ServerAliveInterval 保持稳定
- 无 Agent Forwarding / X11 Forwarding
