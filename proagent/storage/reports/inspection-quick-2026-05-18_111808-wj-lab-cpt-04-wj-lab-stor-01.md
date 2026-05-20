# 巡检报告 — wj-lab-cpt-04 + wj-lab-stor-01

**生成时间**: 2026-05-18 11:18:08
**巡检类型**: quick
**目标系统**: wj-lab-cpt-04 + wj-lab-stor-01
**整体状态**: 🟡 注意

---

## 摘要

两节点运行正常，Ceph 集群健康（HEALTH_OK），存储容量充裕（使用率 3.85%）。GPU 节点存在 GPU 2 高负载运行（100% 利用率），建议关注热点进程。

## 关键指标

```
**wj-lab-cpt-04 (GPU Worker)**:
- CPU: 负载 6.78/8.41/9.21 (64核), per-core ≈ 0.14 → 🟢
- 内存: 257GB, 使用 34.6GB (13%) → 🟢
- 磁盘: / 52%, /mnt/jfs200G 1% → 🟢
- 服务: 无 failed units → 🟢
- GPU: 4x RTX 5090, GPU 2 利用率 100% @ 41°C → 🟡

**wj-lab-stor-01 (Ceph Storage)**:
- CPU: 负载 0.11/1.18/1.05 (32核) → 🟢
- Ceph: HEALTH_OK, 30 OSD up, 使用率 3.85% → 🟢
```

## 发现的问题

1. GPU 2 (RTX 5090) 利用率 100%，运行热点进程 python myapp/tools/watch_workflow.py (CPU 99.6%)
2. wj-lab-cpt-04 15分钟负载偏高 (9.21)，主要来自容器和 Python 工作流
3. / 根分区使用率 52%，需关注日志增长

---

> 由 ProAgent SRE Agent 自动生成。本巡检为只读操作，未执行任何系统变更。
