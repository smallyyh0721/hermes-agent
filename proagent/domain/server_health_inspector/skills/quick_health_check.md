# Quick Health Check

## When to use
- 定时巡检（每小时一次）
- 用户问"服务器状态如何？"
- 快速概览系统健康

## Inputs required
- target: 目标服务器 ID（可选，默认使用配置的默认目标）

## Procedure

1. 获取系统基本信息
   ```
   server_shell(command="hostname && uptime")
   ```

2. 检查 CPU 负载
   ```
   server_shell(command="cat /proc/loadavg && nproc")
   ```

3. 检查内存使用
   ```
   server_shell(command="free -m")
   ```

4. 检查磁盘使用
   ```
   server_shell(command="df -hT | grep -v tmpfs | grep -v devtmpfs")
   ```

5. 检查 failed services
   ```
   server_shell(command="systemctl --failed --no-pager 2>/dev/null || echo 'systemctl not available'")
   ```

6. 检查最近错误日志
   ```
   server_shell(command="journalctl --since '1 hour ago' -p err --no-pager 2>/dev/null | tail -10 || dmesg -T | tail -10")
   ```

## Tools allowed
- server_shell (read_only)

## Stop conditions
- 所有 6 步完成
- 任何步骤超时（30s）则跳过并标注

## Output format

```
☤ 快速健康报告 · {hostname} · {timestamp}
状态：🟢/🟡/🔴

📊 概览
- CPU load: {load1}/{load5}/{load15} ({cores} cores)
- 内存: {used}MB / {total}MB ({percent}%)
- Swap: {swap_used}MB / {swap_total}MB
- 磁盘: {most_used_partition} {percent}%

⚠️ 问题 (如有)
- {issue_description}

✅ 正常项
- {normal_items}
```

## Examples

输入: "服务器状态如何？"
输出: 执行上述 6 步，生成结构化报告
