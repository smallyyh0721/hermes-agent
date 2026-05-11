# JuiceFS Health Check

## When to use
- 用户询问 JuiceFS 状态
- 定时存储巡检
- 发现文件系统读写异常

## Inputs required
- target: JuiceFS 客户端节点（需能访问 localhost:9567）

## Procedure

### Phase 1: 基本状态
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_uptime'")
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_used_(space|inodes)'")
```

### Phase 2: 读写延迟
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_object_request_durations_histogram_seconds_(count|sum)' | head -20")
```

### Phase 3: 缓存状态
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_blockcache_(hits|miss|bytes|eviction)'")
```

### Phase 4: 元数据操作
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_transaction_durations_histogram_seconds_(count|sum)'")
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_meta_ops_durations_histogram_seconds_(count|sum)' | head -20")
```

### Phase 5: 错误与重试
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_(object_request_errors|transaction_restart)'")
```

## Tools allowed
- server_shell (read_only, curl only)

## Stop conditions
- metrics endpoint 不可达（超时 5s）
- 所有 Phase 完成

## Output format

```
☤ JuiceFS 健康报告 · {client_node} · {timestamp}
状态：🟢/🟡/🔴

━━━ 概览 ━━━
Uptime: {uptime}
Used: {space} / Inodes: {inodes}

━━━ 性能 ━━━
读延迟: avg {read_avg}ms, P99 {read_p99}ms
写延迟: avg {write_avg}ms, P99 {write_p99}ms
元数据: avg {meta_avg}ms

━━━ 缓存 ━━━
命中率: {hit_rate}%
缓存大小: {cache_bytes}
驱逐: {evictions}

━━━ 异常 ━━━
- {issue}: {detail}

━━━ 建议 ━━━
- {suggestion}（仅建议，不执行）
```

## 阈值参考

| 指标 | 注意 | 异常 |
|------|------|------|
| 读延迟 P99 | > 100ms | > 500ms |
| 写延迟 P99 | > 200ms | > 1s |
| 缓存命中率 | < 80% | < 50% |
| 元数据延迟 P99 | > 50ms | > 200ms |
| 错误数 | > 0/min | > 10/min |
