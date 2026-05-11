# Full Health Inspection

## When to use
- 每日深度巡检（每天 9:00）
- 用户要求"全面检查"
- 发现异常后需要深入排查

## Inputs required
- target: 目标服务器 ID

## Procedure

### Phase 1: 系统信息
```
server_shell(command="hostnamectl 2>/dev/null || (uname -a && cat /etc/os-release)")
server_shell(command="uptime && who")
```

### Phase 2: CPU 深度
```
server_shell(command="cat /proc/loadavg && nproc")
server_shell(command="mpstat 1 3 2>/dev/null || top -bn1 | head -5")
server_shell(command="ps auxf --sort=-%cpu | head -15")
```

### Phase 3: 内存深度
```
server_shell(command="free -m")
server_shell(command="vmstat 1 3")
server_shell(command="ps aux --sort=-%mem | head -15")
server_shell(command="cat /proc/meminfo | grep -E '(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|Dirty|Writeback)'")
```

### Phase 4: 磁盘深度
```
server_shell(command="df -hT | grep -v tmpfs")
server_shell(command="df -i | grep -v tmpfs")
server_shell(command="iostat -x 1 3 2>/dev/null || cat /proc/diskstats")
server_shell(command="lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE")
```

### Phase 5: 网络
```
server_shell(command="ip -br a")
server_shell(command="ss -s")
server_shell(command="ss -tunap | head -30")
```

### Phase 6: 服务状态
```
server_shell(command="systemctl --failed --no-pager 2>/dev/null")
server_shell(command="systemctl list-units --type=service --state=running --no-pager 2>/dev/null | tail -20")
```

### Phase 7: 日志分析
```
server_shell(command="journalctl --since '24 hours ago' -p err --no-pager 2>/dev/null | tail -30")
server_shell(command="dmesg -T 2>/dev/null | grep -iE '(error|fail|warn|oom|kill)' | tail -20")
```

### Phase 8: 安全快检
```
server_shell(command="last -10")
server_shell(command="cat /var/log/auth.log 2>/dev/null | grep -i 'failed' | tail -10 || journalctl -u sshd --since '24h ago' --no-pager 2>/dev/null | grep -i 'failed' | tail -10")
```

## Tools allowed
- server_shell (read_only)

## Stop conditions
- 所有 8 个 Phase 完成
- 单步超时跳过并标注
- 总时间不超过 120s

## Output format

```
☤ 深度健康报告 · {hostname} · {timestamp}
状态：🟢/🟡/🔴

━━━ 系统信息 ━━━
OS: {os_info}
Kernel: {kernel}
Uptime: {uptime}

━━━ CPU ━━━
Load: {load} ({judgment})
Top processes: ...

━━━ 内存 ━━━
Usage: {used}/{total} ({percent}%)
Swap: {swap_info}
Top consumers: ...

━━━ 磁盘 ━━━
{partition_table}
IO: {io_summary}

━━━ 网络 ━━━
Connections: {conn_summary}
Interfaces: {if_summary}

━━━ 服务 ━━━
Failed: {failed_count}
{failed_list}

━━━ 日志异常 ━━━
{log_summary}

━━━ 安全 ━━━
{security_summary}

━━━ 总结 ━━━
⚠️ 需关注: {issues}
💡 建议: {suggestions}
```

## Examples

输入: "全面检查 web-01"
输出: 执行全部 8 个 Phase，生成完整报告
