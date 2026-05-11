# Ceph Health Check

## When to use
- 用户询问 Ceph 集群状态
- 定时存储巡检
- 发现存储相关异常需要排查

## Inputs required
- target: Ceph 节点（需能访问 9283/9100 端口）
- metrics_host: Ceph exporter 地址（默认 10.11.4.20）

## Procedure

### Phase 1: 集群健康概览
```
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_health_status'")
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_cluster_total_(bytes|used_bytes)'")
```

### Phase 2: OSD 状态
```
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_osd_(up|in) ' | head -30")
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_osd_apply_latency_ms' | sort -t' ' -k2 -rn | head -10")
```

### Phase 3: PG 状态
```
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_pg_(degraded|undersized|stale|inconsistent)'")
```

### Phase 4: IOPS 与吞吐
```
server_shell(command="curl -s http://10.11.4.20:9283/metrics | grep -E '^ceph_osd_op_(r|w|rw)_bytes'")
```

### Phase 5: 节点磁盘 IO（Node Exporter）
```
server_shell(command="curl -s http://10.11.4.20:9100/metrics | grep -E '^node_disk_(io_time_seconds_total|read_bytes_total|written_bytes_total)' | head -20")
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
