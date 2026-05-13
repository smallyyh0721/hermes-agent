# JuiceFS Health Check

## When to use
- 用户询问 JuiceFS 状态、性能、空间
- 定时存储巡检
- 发现文件系统读写异常、延迟高

## Inputs required
- target: JuiceFS 客户端节点（默认 wj-lab-cpt-04，JuiceFS 挂载在此）
- mountpoint: /mnt/jfs200G
- volume name: jfs200

## Procedure

### Phase 1: 卷状态与连接
```
server_shell(command="juicefs status jfs200 2>/dev/null || echo 'juicefs CLI not available'", target="wj-lab-cpt-04")
```

### Phase 2: 实时性能统计
```
server_shell(command="juicefs stats /mnt/jfs200G --interval 3 --count 1 2>/dev/null || echo 'stats not available'", target="wj-lab-cpt-04")
```

### Phase 3: 空间使用概览
```
server_shell(command="juicefs summary /mnt/jfs200G --depth 1 2>/dev/null || df -h /mnt/jfs200G", target="wj-lab-cpt-04")
```

### Phase 4: 缓存与 Metrics
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_(blockcache_hits|blockcache_miss|blockcache_bytes|used_space|used_inodes)' | head -10", target="wj-lab-cpt-04")
```

### Phase 5: 读写延迟（Metrics）
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_object_request_durations_histogram_seconds_(sum|count)' | head -10", target="wj-lab-cpt-04")
```

### Phase 6: 元数据操作延迟
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_(transaction_durations|meta_ops_durations)_histogram_seconds_(sum|count)' | head -10", target="wj-lab-cpt-04")
```

### Phase 7: 错误与重试
```
server_shell(command="curl -s http://localhost:9567/metrics | grep -E '^juicefs_(object_request_errors|transaction_restart)' | head -5", target="wj-lab-cpt-04")
```

## 深度诊断命令（按需使用）

当发现异常时，可进一步使用：

```
# 查看特定目录的 chunk 分布和元数据
server_shell(command="juicefs info /mnt/jfs200G/<path>", target="wj-lab-cpt-04")

# 实时访问模式分析（5 秒采样）
server_shell(command="juicefs profile /mnt/jfs200G --interval 5 --count 1 2>/dev/null", target="wj-lab-cpt-04")

# 收集完整诊断信息
server_shell(command="juicefs debug /mnt/jfs200G 2>/dev/null | head -50", target="wj-lab-cpt-04")

# 查看卷配置
server_shell(command="juicefs config redis://10.11.4.20:6379/1 2>/dev/null | head -20", target="wj-lab-cpt-04")
```

## Tools allowed
- server_shell (read_only)

## Stop conditions
- juicefs CLI 不可用时降级为 curl metrics
- 所有 Phase 完成
- 单步超时跳过

## Output format

```
☤ JuiceFS 健康报告 · wj-lab-cpt-04 · {timestamp}
状态：🟢/🟡/🔴

━━━ 卷状态 ━━━
Volume: jfs200
Sessions: {count}
Mountpoint: /mnt/jfs200G

━━━ 性能 ━━━
FUSE ops/s: {ops}
读延迟: avg {read_avg}ms
写延迟: avg {write_avg}ms
元数据延迟: avg {meta_avg}ms

━━━ 空间 ━━━
Used: {space}
Inodes: {inodes}
Top dirs: ...

━━━ 缓存 ━━━
命中率: {hit_rate}%
缓存大小: {cache_bytes}

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
| FUSE ops 延迟 | > 50ms avg | > 200ms avg |
