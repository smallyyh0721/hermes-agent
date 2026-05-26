# 巡检报告 — storage-cluster

**生成时间**: 2026-05-26 10:52:41
**巡检类型**: quick
**目标系统**: storage-cluster
**整体状态**: 🟢 健康

---

## 摘要

存储集群健康。Ceph 30 个 OSD 全部正常，容量使用 4.1%，无告警。JuiceFS jfs200 卷正常，17 个活跃连接，容量使用 2.23TB/65.97PB。

## 关键指标

```
## Ceph 集群
- Health: HEALTH_OK ✓
- OSD: 30 up, 30 in (全部正常)
- MON: 3 daemons (wj-lab-stor-01/02/03), quorum 正常
- MGR: active (wj-lab-stor-02) + standby
- RGW: 3 daemons active
- 容量: 8.6 TiB / 210 TiB (4.1% used)
- Objects: 902.89k, PGs: 385 active+clean
- IO: 6.2 KiB/s read, 1.0 MiB/s write

## JuiceFS (jfs200)
- 后端存储: S3 (http://juicefs.10.11.4.30:8000)
- 配置容量: 65.97 PB
- 当前使用: 2.23 TB (约 0.003%)
- Inodes: 64,815 / 10,485,760 (0.6%)
- 活跃 Sessions: 17 个
  - 控制节点: wj-lab-ctl-01/02/03
  - 计算节点: wj-lab-cpt-01/02/03/04
  - K8s PVC: 多个动态卷

## 存储节点 wj-lab-stor-01
- CPU: 108 核心
- 内存: 256 GB, 可用 201 GB (74.5% 可用)
- /database (NVMe): 7.68 TB, 可用 7.63 TB (0.7% used)
- / (系统盘): 942 GB, 可用 778 GB (17% used)
```

## 发现的问题

none

---

> 由 ProAgent SRE Agent 自动生成。本巡检为只读操作，未执行任何系统变更。
