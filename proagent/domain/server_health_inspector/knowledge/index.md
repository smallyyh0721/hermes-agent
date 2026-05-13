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

## 存储监控（Ceph + JuiceFS）

### Ceph Metrics 获取
- Node Exporter (含存储节点指标): `curl -s http://10.11.4.20:9100/metrics`
- Ceph CLI (需要 sudo): `sudo ceph status`, `sudo ceph osd tree`, `sudo ceph health detail`
- 关键 node_exporter 前缀: `node_disk_`, `node_filesystem_`, `node_network_`
- Ceph 进程检查: `ps aux | grep ceph-osd`
- **注意**: yuyonghao 用户无 ceph 权限，所有 ceph 命令必须加 `sudo`

### JuiceFS Metrics 获取
- 客户端 Metrics: `curl -s http://localhost:9567/metrics`
- 关键前缀: `juicefs_object_request_`, `juicefs_blockcache_`, `juicefs_transaction_`, `juicefs_used_`

### JuiceFS CLI 命令（在 wj-lab-cpt-04 上执行）
- **卷状态**: `juicefs status jfs200` — 查看连接数、session 信息
- **实时统计**: `juicefs stats /mnt/jfs200G` — FUSE ops/s、延迟、吞吐
- **空间统计**: `juicefs summary /mnt/jfs200G --depth 1` — 目录级空间占用
- **文件信息**: `juicefs info /mnt/jfs200G/<path>` — chunk 分布、元数据
- **访问分析**: `juicefs profile /mnt/jfs200G --interval 5` — 热点文件、访问模式
- **诊断收集**: `juicefs debug /mnt/jfs200G` — 完整诊断信息
- **卷配置**: `juicefs config redis://10.11.4.20:6379/1` — 查看配置（只读）
- **注意**: JuiceFS 挂载在 wj-lab-cpt-04 的 /mnt/jfs200G，所有 juicefs 命令在该节点执行

### Kubernetes 访问
- **kubectl 在 k8s-master (10.11.4.2) 上执行**
- 命令格式: `server_shell(command="kubectl get ...", target="k8s-master")`
- kubeconfig 位于 k8s-master 的 `~/.kube/config`（默认路径）
- 只读命令: `kubectl get`, `kubectl describe`, `kubectl logs`, `kubectl top`
- 禁止写命令: `kubectl delete/apply/patch/scale` 等（Policy Guard 拦截）

### Prometheus Text Format 解析要点
- 每行格式: `metric_name{label="value"} numeric_value`
- `# HELP` 行是描述，`# TYPE` 行是类型（counter/gauge/histogram）
- histogram 有 `_bucket`, `_sum`, `_count` 后缀
- 计算 P99: 从 bucket 累积分布中插值
- 计算 avg: sum / count

### Ceph 诊断路径
1. **集群不健康** → `ceph status` → 检查 OSD 进程 → 检查节点磁盘 IO
2. **OSD down** → `ps aux | grep ceph-osd` → 检查对应节点 disk IO / 网络
3. **容量告急** → `node_filesystem_avail_bytes` → 找满的磁盘
4. **IO 高** → `node_disk_io_time_seconds_total` → 定位慢盘

### JuiceFS 诊断路径
1. **读写慢** → `juicefs stats /mnt/jfs200G` 看 ops 延迟 → `juicefs profile` 看热点文件
2. **缓存命中低** → metrics 看 `blockcache_hits/(hits+miss)` → `juicefs stats` 确认 cache 命中
3. **元数据慢** → `juicefs stats` 看 meta 延迟 → 检查 Redis 连接（`redis-cli -h 10.11.4.20 ping`）
4. **空间问题** → `juicefs summary /mnt/jfs200G --depth 1` 看大目录 → `juicefs info <path>` 看 chunk
5. **连接异常** → `juicefs status jfs200` 看 session 数 → 检查 mount 进程存活
