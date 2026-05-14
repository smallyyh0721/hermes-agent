# Token Factory 测试 Agent 方案

## 1. 方案定位

本方案面向 Token Factory 平台的自动化测试体系建设，目标是通过 **AI Agent + 传统测试工具** 的组合，提升开发、交付、回归、验收过程中的测试效率和质量。

核心定位：

> 测试 Agent 不是替代所有测试框架，而是围绕 Playwright、pytest、k6/Locust、单元测试框架、GenAI 评测框架，完成测试计划生成、测试用例生成、执行编排、失败诊断、报告生成和知识沉淀。

适用范围：

- UI 测试
- API 测试
- 单元测试
- 回归测试
- 计费测试
- 权限与租户隔离测试
- 性能测试
- 私有化交付验收测试
- LLM / RAG 输出质量测试
- 售后问题复现测试

---

## 2. 建设目标

### 2.1 业务目标

Token Factory 的测试工作会贯穿研发、交付、运维和售后。测试 Agent 的目标是：

1. 减少人工编写测试用例的时间。
2. 减少人工测试遗漏。
3. 提高交付前验收效率。
4. 提升回归测试稳定性。
5. 自动生成客户可读的测试报告。
6. 自动诊断测试失败原因。
7. 将测试经验沉淀成知识库和可复用模板。
8. 支撑私有化交付的标准验收流程。

### 2.2 技术目标

测试 Agent 需要具备：

```text
读取 PRD / OpenAPI / customer-values.yaml
  ↓
生成测试计划
  ↓
生成测试用例
  ↓
调用测试工具执行
  ↓
收集测试结果、截图、trace、日志、监控、账单数据
  ↓
分析失败原因
  ↓
生成测试报告 / 验收报告
  ↓
沉淀失败案例和修复建议
```

---

## 3. 设计原则

### 3.1 Agent 负责智能，测试工具负责执行

不要让 Agent 自己“凭感觉测试”。

正确方式是：

```text
Agent：理解需求、生成用例、编排测试、分析结果、生成报告
测试框架：稳定执行 UI/API/性能/单元测试
```

### 3.2 配置驱动

测试 Agent 应该读取标准配置生成测试计划。

主要输入：

```text
prd.md
openapi.yaml
customer-values.yaml
acceptance-test.yaml
billing-policy.yaml
sla-policy.yaml
model-config.yaml
```

### 3.3 测试可追溯

每次测试必须能追踪：

```text
测试输入
测试用例
执行环境
测试结果
失败日志
截图/trace
Agent 分析结论
人工确认结果
```

### 3.4 高风险结论人工确认

Agent 可以建议，但不能自动放行：

- SLA 失败例外
- 计费异常忽略
- 权限隔离失败忽略
- 客户验收结论
- 生产发布结论

---

## 4. 总体架构

```text
Test Agent Platform

输入层：
- PRD / 需求文档
- OpenAPI / API Schema
- customer-values.yaml
- SLA / 计费规则
- 历史工单 / 缺陷 / 测试报告

Agent 层：
- Test Orchestrator Agent
- UI Test Agent
- API Test Agent
- Unit Test Agent
- Billing Test Agent
- Performance Test Agent
- Regression Test Agent
- LLM Quality Test Agent
- Report Agent

工具层：
- Playwright
- pytest + httpx
- Jest / Vitest / Go test / JUnit
- k6 / Locust
- Qodo Cover 思路 / 自研单测生成器
- Rhesis / EvalScope
- Allure / HTML Report / Markdown Report

结果层：
- 测试报告
- 客户验收报告
- 覆盖率报告
- 性能报告
- 计费对账报告
- 缺陷单
- 知识库条目
```

---

## 5. 技术选型

## 5.1 UI / E2E 测试

### 首选：Playwright

用途：

- 控制台 UI 测试
- 登录流程测试
- API Key 页面测试
- 模型列表页面测试
- 账单页面测试
- 工单页面测试
- AIGC 任务页面测试
- 截图、trace、console error 收集

原因：

- 跨浏览器支持
- 自动等待
- trace viewer 成熟
- 适合 CI
- 可被 Agent 调用
- 支持 accessibility snapshot，适合 AI agent 工作流

### 可选增强：TestZeus Hercules

用途：

- 自然语言 / Gherkin 驱动 UI 测试
- 无代码验收测试
- UI + API + 视觉验证
- 交付验收测试

适合场景：

- 交付人员不会写测试代码
- 售前/实施团队用自然语言描述测试步骤
- 快速生成客户验收测试

注意：

- 需要评估 license
- 不建议一开始深度集成生产流程
- 可先作为实验工具

### 可选增强：Passmark

用途：

- AI 回归测试
- UI 自愈回归
- 页面变化后自动寻找新的交互路径

适合场景：

- Token Factory 控制台频繁迭代
- 页面布局变化导致 selector 维护成本高

---

## 5.2 API 测试

### 首选：pytest + httpx

用途：

- OpenAI-compatible API 测试
- Chat Completions 测试
- Streaming 测试
- Embedding 测试
- Rerank 测试
- Usage API 测试
- Billing API 测试
- API Key 权限测试
- 错误码测试

原因：

- Python 生态适合和 Agent、计费、日志、报告系统集成
- 易于生成用例
- 易于做精确断言

### 可选：Postman / Newman

适合：

- 售前演示
- 轻量接口集合测试
- 给客户交付 Postman Collection

### 可选：Schemathesis

适合：

- OpenAPI schema fuzz 测试
- 异常参数测试

---

## 5.3 单元测试

### 常规测试框架

按语言选择：

| 语言 | 推荐 |
|---|---|
| Python | pytest |
| TypeScript / JavaScript | Vitest / Jest |
| Go | go test |
| Java | JUnit |
| Rust | cargo test |

### AI 单测生成

推荐路线：

```text
参考 Qodo Cover 架构
+ Codex 自定义 Unit Test Agent
+ 结合覆盖率报告自动补测试
```

适合生成测试的模块：

- token 计量
- 账单计算
- 价格策略
- API Key 权限
- 租户隔离逻辑
- 配置校验
- resource planner 规则
- SLA 策略
- 限流策略

不建议完全交给 AI 的模块：

- 计费核心逻辑的最终验收
- 安全策略最终判断
- 数据删除逻辑

这些必须人工 review。

---

## 5.4 性能测试

### 首选：k6 / Locust

用途：

- API 性能压测
- 并发测试
- 包并发验收
- 限流测试
- P95/P99 延迟测试
- 稳定性测试

选择建议：

| 工具 | 适合 |
|---|---|
| k6 | 标准 HTTP API 压测、CI 友好 |
| Locust | 更复杂用户行为模拟、Python 生态 |

### Agent 能力

Performance Test Agent 负责：

- 根据 SLA 生成压测计划
- 生成 k6/Locust 脚本
- 执行压测
- 收集 TTFT、TPOT、P95、P99、错误率
- 分析瓶颈
- 生成性能报告

---

## 5.5 LLM / RAG 输出质量测试

### 可选：Rhesis / EvalScope / OpenCompass

用途：

- LLM 输出质量回归
- RAG 答案质量测试
- Prompt regression
- 模型升级回归
- 安全与拒答测试

适合后续阶段。

MVP 阶段可以先只做简单规则：

- 输出非空
- JSON 格式合法
- Function calling 格式正确
- RAG 是否包含引用
- 敏感问题是否拒答

---

## 5.6 报告系统

推荐：

- Allure Report
- Markdown Report
- HTML Report
- PDF Report
- JUnit XML
- JSON 原始结果

测试 Agent 应自动生成：

- 内部测试报告
- 客户验收报告
- 性能报告
- 账单对账报告
- 缺陷分析报告

---

## 6. PRD

## 6.1 产品名称

```text
Token Factory Test Agent
```

## 6.2 产品定位

Token Factory Test Agent 是面向 Token Factory 研发、交付和运维场景的智能测试编排系统，用于自动生成、执行、分析和报告 UI、API、计费、性能、单元、回归和交付验收测试。

## 6.3 目标用户

| 用户 | 诉求 |
|---|---|
| 研发工程师 | 自动生成单元测试、API 测试、回归测试 |
| 测试工程师 | 快速生成测试计划、执行回归、定位失败原因 |
| 交付工程师 | 私有化交付前自动验收 |
| SRE | 性能、稳定性、回归问题自动诊断 |
| 售后支持 | 快速复现客户问题 |
| 产品经理 | 从测试和缺陷中发现产品改进点 |
| 客户 | 获得清晰、可信的验收报告 |

## 6.4 核心用户故事

### 用户故事 1：根据 PRD 生成测试计划

作为测试负责人，我希望上传 PRD 或输入功能描述，系统能够自动生成 UI、API、计费、权限和性能测试计划。

验收标准：

- 能识别功能模块
- 能生成测试分类
- 能生成测试用例摘要
- 能标记 P0/P1/P2 优先级
- 能导出 Markdown / YAML

---

### 用户故事 2：根据 customer-values.yaml 生成交付验收测试

作为交付工程师，我希望系统读取客户配置，自动生成交付验收测试计划。

验收标准：

- 能识别客户开通的模型
- 能识别 SLA
- 能识别计费规则
- 能识别是否启用 AIGC
- 能生成 acceptance-test.yaml
- 能生成客户验收报告模板

---

### 用户故事 3：自动执行 UI 测试

作为交付工程师，我希望系统自动打开控制台并验证关键 UI 流程。

验收标准：

- 登录成功
- 模型列表可见
- API Key 可创建、禁用
- 用量页面可查看
- 账单页面可导出
- 截图和 trace 被保存

---

### 用户故事 4：自动执行 API 测试

作为测试工程师，我希望系统自动测试 Token Factory 的标准 API。

验收标准：

- `/v1/models` 正常
- `/v1/chat/completions` 正常
- 流式输出正常
- `/v1/embeddings` 正常
- `/v1/rerank` 正常
- 非法参数返回预期错误
- 未授权模型返回 403
- 错误 API Key 返回 401

---

### 用户故事 5：自动执行计费测试

作为财务/交付负责人，我希望系统验证 token 计量和账单金额是否正确。

验收标准：

- input token 计量正确
- output token 计量正确
- usage ledger 记录正确
- billing invoice 金额正确
- 不同项目/API Key 归属正确
- 导出账单数据一致

---

### 用户故事 6：自动执行性能验收

作为企业客户，我希望平台交付前证明其满足并发和延迟承诺。

验收标准：

- 能按 SLA 生成压测计划
- 能输出 TTFT / TPOT / P95 / P99
- 能输出成功率和错误率
- 能判断是否达标
- 能生成性能报告

---

### 用户故事 7：自动生成单元测试

作为开发工程师，我希望系统根据代码变更和覆盖率报告自动生成单元测试。

验收标准：

- 能读取 PR diff
- 能识别低覆盖率文件
- 能生成测试用例
- 能运行测试
- 能输出覆盖率变化
- 需要人工 review 后合并

---

### 用户故事 8：失败自动诊断

作为测试负责人，我希望测试失败后 Agent 自动分析可能原因。

验收标准：

- 能关联错误日志
- 能关联监控指标
- 能关联最近变更
- 能生成失败原因候选
- 能给出修复建议
- 能自动创建缺陷单

---

### 用户故事 9：自动生成客户验收报告

作为交付负责人，我希望系统在测试完成后自动生成客户可读的验收报告。

验收标准：

- 有测试总览
- 有通过/失败结论
- 有 UI 截图
- 有 API 样例
- 有计费对账
- 有性能图表
- 有风险和遗留问题
- 可导出 PDF / HTML / Markdown

---

## 7. 功能模块

## 7.1 Test Plan Generator

输入：

- PRD
- OpenAPI
- customer-values.yaml
- SLA policy
- billing policy

输出：

- 测试计划
- 测试用例列表
- acceptance-test.yaml

---

## 7.2 UI Test Executor

能力：

- Playwright 测试执行
- 截图
- trace
- console error 捕获
- 页面元素断言

---

## 7.3 API Test Executor

能力：

- pytest/httpx 测试执行
- API schema 校验
- 正常请求测试
- 异常请求测试
- 鉴权测试
- 限流测试

---

## 7.4 Billing Test Executor

能力：

- 构造固定 token 请求
- 读取 usage ledger
- 读取 invoice
- 对账
- 生成差异报告

---

## 7.5 Performance Test Executor

能力：

- 生成 k6/Locust 脚本
- 执行压测
- 收集性能指标
- 判断 SLA 是否达标

---

## 7.6 Unit Test Generator

能力：

- 读取 PR diff
- 读取覆盖率报告
- 生成单元测试
- 执行单元测试
- 输出覆盖率变化

---

## 7.7 Regression Test Manager

能力：

- 管理回归测试集
- 根据变更选择测试范围
- 自动执行回归
- 识别高风险变更

---

## 7.8 Failure Diagnosis Agent

能力：

- 分析测试失败
- 查询日志
- 查询监控
- 查询最近部署变更
- 生成原因和修复建议

---

## 7.9 Report Generator

能力：

- 生成 HTML / Markdown / PDF 报告
- 汇总截图、trace、日志、性能图表
- 生成客户验收报告
- 生成内部缺陷报告

---

## 8. MVP 方案

## 8.1 MVP 目标

用 4-6 周建设一个最小可用版本，覆盖：

```text
UI 测试
API 测试
计费测试
性能测试
报告生成
```

MVP 不追求全 AI 化，而是先完成：

```text
配置驱动测试计划
+ 传统测试框架执行
+ Agent 生成报告和失败分析
```

---

## 8.2 MVP 范围

### P0 功能

1. 读取 `acceptance-test.yaml`。
2. 执行 Playwright UI 测试。
3. 执行 pytest/httpx API 测试。
4. 执行基础计费对账测试。
5. 执行 k6/Locust 简单性能测试。
6. 收集截图、日志、trace、原始结果。
7. 生成 Markdown/HTML 验收报告。
8. Agent 生成失败原因摘要。

### 暂不做

- 复杂自愈 UI 测试
- 全自动单元测试 PR
- RAG 输出质量深度评测
- AIGC 视频复杂验收
- 生产自动修复
- 完整测试平台 UI

---

## 8.3 MVP 技术栈

| 模块 | 技术 |
|---|---|
| UI 测试 | Playwright |
| API 测试 | pytest + httpx |
| 计费测试 | pytest + SQL/HTTP 查询 usage/billing |
| 性能测试 | k6 或 Locust |
| 报告 | Markdown + HTML + JUnit XML |
| Agent | Codex / 内部 LLM Agent |
| 配置 | YAML |
| CI | GitHub Actions / GitLab CI / Jenkins |

---

## 8.4 MVP 输入配置

```yaml
apiVersion: tokenfactory.ai/v1
kind: AcceptanceTestPlan

metadata:
  customer_id: demo-customer
  environment: staging

spec:
  target:
    console_url: "https://console.demo.local"
    api_base_url: "https://api.demo.local/v1"

  auth:
    admin_user: "admin"
    api_key_secret_ref: "demo-api-key"

  models:
    chat:
      - qwen-32b-chat
    embedding:
      - bge-m3
    rerank:
      - bge-reranker-v2

  ui_tests:
    enabled: true
    cases:
      - login
      - model_list
      - api_key_create_disable
      - usage_page
      - billing_export

  api_tests:
    enabled: true
    cases:
      - models
      - chat_completion
      - chat_streaming
      - embedding
      - rerank
      - unauthorized_model
      - invalid_api_key

  billing_tests:
    enabled: true
    tolerance:
      token_percent: 1
      amount_cny: 0.01

  performance_tests:
    enabled: true
    scenarios:
      - name: short_chat
        model: qwen-32b-chat
        input_tokens: 512
        output_tokens: 256
        concurrency: 32
        duration_seconds: 600
        expected:
          success_rate: 0.99
          p99_latency_ms: 8000
          ttft_p95_ms: 1500

  report:
    formats:
      - markdown
      - html
    include_screenshots: true
    include_raw_results: true
```

---

## 8.5 MVP 输出

```text
reports/
  acceptance-report.md
  acceptance-report.html
  junit.xml
  api-test-results.json
  billing-reconciliation.xlsx
  performance-summary.json
  screenshots/
  traces/
  logs/
```

报告内容：

```text
1. 测试概览
2. 环境信息
3. UI 测试结果
4. API 测试结果
5. 计费测试结果
6. 性能测试结果
7. 失败原因分析
8. 风险和建议
9. 验收结论
```

---

## 9. Agent 工作流

## 9.1 测试计划生成

```text
PRD / customer-values.yaml
  ↓
Test Orchestrator Agent
  ↓
生成 acceptance-test.yaml
  ↓
人工 Review
```

---

## 9.2 测试执行

```text
acceptance-test.yaml
  ↓
Test Runner
  ├── Playwright
  ├── pytest/httpx
  ├── Billing Test
  └── k6/Locust
  ↓
原始测试结果
```

---

## 9.3 失败诊断

```text
测试失败
  ↓
Failure Diagnosis Agent
  ↓
读取：
- 错误日志
- 截图
- trace
- API 响应
- 监控指标
- 最近变更
  ↓
输出：
- 失败原因候选
- 影响范围
- 修复建议
- 是否阻塞交付
```

---

## 9.4 报告生成

```text
测试结果 + Agent 分析
  ↓
Report Agent
  ↓
生成：
- 内部测试报告
- 客户验收报告
- 缺陷单
- 知识库条目
```

---

## 10. 测试覆盖设计

## 10.1 UI 测试覆盖

P0：

- 登录
- 模型列表
- API Key 创建 / 禁用
- 用量页面
- 账单导出

P1：

- 工单页面
- 预算告警页面
- 专属实例页面
- AIGC 任务页面
- 权限角色切换

---

## 10.2 API 测试覆盖

P0：

- `/v1/models`
- `/v1/chat/completions`
- streaming chat
- `/v1/embeddings`
- `/v1/rerank`
- 错误 API Key
- 未授权模型
- 非法参数

P1：

- `/v1/usage`
- `/v1/billing`
- `/v1/batches`
- AIGC API
- Webhook

---

## 10.3 计费测试覆盖

P0：

- input token
- output token
- 项目维度汇总
- API Key 维度汇总
- 模型维度汇总
- invoice 金额

P1：

- cached token
- GPU-hour
- image unit
- video seconds
- 预算告警
- 超额计费

---

## 10.4 性能测试覆盖

P0：

- short chat 32 并发
- 8K RAG 16 并发
- 限流测试

P1：

- 长上下文
- 包并发验收
- 稳定性 4-8 小时
- AIGC 队列吞吐

---

## 10.5 单元测试覆盖

P0：

- token 计量
- price policy
- billing calculation
- API Key 权限
- customer config validation

P1：

- routing policy
- SLA policy
- resource planner
- budget alert
- isolation policy

---

## 11. 实施路线图

## 阶段 0：准备，1 周

产出：

- 测试范围定义
- acceptance-test.yaml schema
- 测试用例模板
- 报告模板
- 测试环境准备

---

## 阶段 1：MVP，4-6 周

完成：

- Playwright UI 测试
- pytest API 测试
- 基础计费测试
- k6/Locust 性能测试
- Markdown/HTML 报告
- Agent 失败分析摘要

---

## 阶段 2：交付验收集成，4-8 周

完成：

- 根据 customer-values.yaml 自动生成测试计划
- 自动生成客户验收报告
- 集成交付流水线
- 集成工单系统
- 失败自动创建缺陷单

---

## 阶段 3：AI 增强测试，8-12 周

完成：

- Hercules / Passmark PoC
- 单元测试自动生成
- LLM/RAG 质量回归
- 自动测试用例推荐
- 测试失败知识库沉淀

---

## 阶段 4：测试智能闭环，长期

完成：

- 测试 Agent 与售后 Agent 联动
- 根据线上故障自动生成回归用例
- 根据客户工单补充测试集
- 根据缺陷趋势优化测试策略
- 版本发布自动风险评估

---

## 12. 组织与职责

| 角色 | 职责 |
|---|---|
| 测试负责人 | 定义测试策略和验收标准 |
| 测试工程师 | 维护测试框架和用例模板 |
| Agent 工程师 | 维护测试 Agent 和工具调用 |
| 研发工程师 | Review AI 生成单元测试 |
| 交付工程师 | 执行客户验收测试 |
| SRE | 提供监控和日志接口 |
| 产品经理 | 定义 PRD 验收标准 |

---

## 13. 风险与控制

## 13.1 AI 生成测试不可靠

控制：

- 所有测试必须可运行
- 所有关键断言人工 review
- 生成测试必须进入 CI

## 13.2 Agent 误判测试结果

控制：

- Agent 只生成分析，不直接决定交付通过
- 验收结论需要人工确认

## 13.3 UI AI 自愈误操作

控制：

- 生产数据环境禁用破坏性操作
- 测试环境使用专用账号和测试数据

## 13.4 计费测试风险

控制：

- 计费用例必须固定
- 金额计算必须可追溯
- 计费差异必须人工确认

## 13.5 开源 license 风险

控制：

- Hercules 等 AGPL 工具先做 PoC
- 商业集成前完成法务评估
- 核心平台优先使用 Apache/MIT/BSD 许可工具

---

## 14. 推荐落地顺序

第一阶段不要引入太多 AI 测试工具。

推荐顺序：

```text
1. Playwright + pytest + k6/Locust
2. acceptance-test.yaml 配置驱动
3. Report Agent 自动生成报告
4. Failure Diagnosis Agent 自动分析失败
5. Codex Unit Test Agent 补单元测试
6. Hercules / Passmark 做 PoC
7. Rhesis / EvalScope 做 LLM 输出质量测试
```

---

## 15. 最终总结

Token Factory Test Agent 的核心价值是：

> 用 Agent 负责测试计划生成、测试用例生成、执行编排、失败诊断和报告生成，用成熟测试工具负责稳定执行。

MVP 不需要一开始做成完整 AI 测试平台，而应先实现：

```text
配置驱动验收测试
+ UI/API/计费/性能自动执行
+ 自动报告
+ Agent 失败分析
```

最终目标是形成一套可复用、可追溯、可自动改进的测试体系，支撑 Token Factory 的开发、私有化交付、回归测试、售后复现和持续质量改进。

