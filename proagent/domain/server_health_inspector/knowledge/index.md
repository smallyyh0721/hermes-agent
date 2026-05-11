# Server Health Inspector - Knowledge Index

## 巡检知识体系

### 硬件层
- CPU: load average 含义（1/5/15分钟）、per-core 标准化、iowait 与磁盘瓶颈关系
- 内存: buffers/cache 的正确解读、swap 使用的含义、OOM killer 机制
- 磁盘: inode vs block 使用率、iostat 指标解读（await/svctm/util）、SMART 预警
- 网络: TIME_WAIT 堆积、conntrack 表满、带宽 vs PPS 瓶颈

### OS 层
- systemd: unit 状态机、依赖关系、journal 日志级别
- 内核: dmesg 关键错误模式（MCE/ECC/hung_task/soft lockup）
- 资源限制: ulimit/sysctl 关键参数、文件句柄泄漏排查
- 时间: NTP 漂移影响、chrony vs systemd-timesyncd

### 进程层
- 进程状态: D(uninterruptible sleep) 与 IO 阻塞、Z(zombie) 清理
- 内存泄漏: RSS 持续增长模式、/proc/[pid]/smaps 分析
- CPU 热点: 用户态 vs 内核态、上下文切换开销

### 日志分析
- 关键模式: segfault、OOM、disk error、link down、authentication failure
- 时间相关性: 问题发生时间线重建

## 常用诊断路径

1. **高 CPU** → `mpstat` → 确认 user/sys/iowait → `ps aux --sort=-%cpu` → 定位进程
2. **高内存** → `free -m` → 确认 available → `ps aux --sort=-%mem` → 检查 swap
3. **磁盘满** → `df -hT` → 定位分区 → `du -x --max-depth=2` → 找大目录
4. **IO 高** → `iostat -x 1 3` → 确认 await/util → `iotop`(如有) → 定位进程
5. **网络问题** → `ss -s` → 连接状态统计 → `ss -tunap` → 具体连接 → `ping/traceroute`
6. **服务异常** → `systemctl --failed` → `journalctl -u <service> --since "1h ago"`
