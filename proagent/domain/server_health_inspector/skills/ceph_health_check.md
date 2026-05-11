# Ceph Health Check

## When to use
- 用户询问 Ceph 集群状态
- 定时存储巡检
- 发现存储相关异常需要排查

## Inputs required
- target: Ceph/存储节点（需能访问 9100 端口）
- metrics_host: Node Exporter 地址（默认 10.11.4.20）

## Procedure

### Phase 1: 节点磁盘状态
```
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_filesystem_(avail|size)_bytes' | grep -v tmpfs")
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_disk_(io_time_seconds_total|read_bytes_total|written_bytes_total)' | head -20")
```

### Phase 2: 磁盘健康与 IO
```
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_disk_(reads_completed_total|writes_completed_total|io_now)' | head -20")
```

### Phase 3: 网络状态（存储网络）
```
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_network_(receive|transmit)_bytes_total' | grep -v 'lo' | head -10")
```

### Phase 4: CPU 与内存（存储节点负载）
```
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_(cpu_seconds_total|memory_MemAvailable_bytes|memory_MemTotal_bytes)' | head -10")
```

### Phase 5: Ceph 进程状态（通过 SSH 直接检查）
```
server_shell(command="ps aux | grep -E '(ceph-osd|ceph-mon|ceph-mgr|ceph-mds)' | grep -v grep")
server_shell(command="ceph status 2>/dev/null || echo 'ceph CLI not available on this node'")
server_shell(command="ceph osd tree 2>/dev/null | head -30 || echo 'ceph CLI not available'")
```

## Tools allowed
- server_shell (read_only, curl only)

## Stop conditions
- metrics endpoint 不可达（超时 5s）
- 所有 Phase 完成

## Output format

```
☤ Ceph 集群健康报告 · {timestamp}
状态：🟢/🟡/🔴

━━━ 集群概览 ━━━
Health: {HEALTH_OK/WARN/ERR}
容量: {used}/{total} ({percent}%)
OSD: {up_count}/{total_count} up, {in_count} in

━━━ 异常项 ━━━
- {issue}: {detail}

━━━ 性能 ━━━
延迟: avg {avg_latency}ms, max {max_latency}ms
IOPS: read {r_iops}, write {w_iops}

━━━ 建议 ━━━
- {suggestion}（仅建议，不执行）
```

## 阈值参考

| 指标 | 注意 | 异常 |
|------|------|------|
| ceph_health_status | ≠ 0 | = 2 |
| OSD down | any | > 1 |
| 容量使用率 | > 75% | > 85% |
| apply_latency_ms | > 20 | > 100 |
| PG degraded | > 0 | 持续 > 5min |
