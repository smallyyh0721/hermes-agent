# 巡检报告 — storage-cluster

**生成时间**: 2026-05-26 09:24:18
**巡检类型**: quick
**目标系统**: storage-cluster
**整体状态**: 🟢 健康

---

## 摘要

存储集群健康，所有组件正常运行。Ceph 有 10 个 OSD，JuiceFS 卷使用率仅 1%，无异常告警。

## 关键指标

```
**Ceph 存储节点 (wj-lab-stor-01)**
- Ceph 进程: 1x mon + 1x mgr + 10x osd (osd.0~osd.9) 全部运行中
- 磁盘容量:
  - /database (NVMe): 7.68TB / 7.63TB 可用 (使用 0.7%)
  - / (root): 943GB / 778GB 可用 (使用 17.5%)
- 内存: 256GB 总计, 187GB 可用 (73% 可用)
- IO 状态: dm-0~dm-9 活跃, dm-8 最高 (io_time=69228s)

**JuiceFS 卷 (jfs200)**
- 挂载点: /mnt/jfs200G (wj-lab-cpt-04)
- 容量: 60TB 总计, 176GB 已用 (使用率 1%)
- inode: 64,726 已用 / 10,485,760 总计
- 活跃会话: 17 个 (来自 6 个节点: wj-lab-ctl-01~03, wj-lab-cpt-01~04, wj-lab-dev-01, 多个 PVC)
- 缓存命中: 0 (当前无 I/O 活动)
- 存储后端: S3 (http://juicefs.10.11.4.30:8000)
- 元数据: Redis Sentinel (10.11.4.20,10.11.4.21,10.11.4.22:26379)
```

## 发现的问题

none

---

> 由 ProAgent SRE Agent 自动生成。本巡检为只读操作，未执行任何系统变更。
