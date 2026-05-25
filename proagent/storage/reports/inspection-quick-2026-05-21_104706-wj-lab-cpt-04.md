# 巡检报告 — wj-lab-cpt-04

**生成时间**: 2026-05-21 10:47:06
**巡检类型**: quick
**目标系统**: wj-lab-cpt-04
**整体状态**: 🟡 注意

---

## 摘要

wj-lab-cpt-04 整体健康，存在 4 个需要关注的问题：Zombie git 进程(4个)、ens2f1np1 网卡 DOWN、systemd-networkd-wait-online 失败、GPU2 满载。其余核心指标（CPU/内存/磁盘/JuiceFS）均正常。

## 关键指标

```
【系统】Ubuntu 22.04 / 内核 5.15.0-174 / 运行 36天18h / 128核
【CPU】负载 15.11 (per-core=0.12) / idle 91% / iowait 0%
【内存】257GB / 已用 36GB (14%) / 可用 217GB / Swap 0
【磁盘】系统盘 /dev/nvme0n1p2: 53% / 数据盘 /dev/nvme1n1: 41% / JuiceFS jfs200: 1%
【网络】ens2f0np0 UP 10.11.4.13 / ens2f1np1 DOWN / roce200 UP 10.11.0.13 / TCP 3019 connections
【GPU】4x NVIDIA RTX 5090 (32GB) / GPU0=0% 35°C / GPU1=0% 32°C / GPU2=100% 41°C / GPU3=0% 31°C
【JuiceFS】v1.3.1+2025-12-02 / cache 103GB / obj_errors=0 / tx_p99≈0.5ms
【文件句柄】23872/2097152 (1.1%)
```

## 发现的问题

1. [🟡 注意] 4 个 zombie git 进程 (PIDs: 3929434, 3929872, 3972974, 3973252)
2. [🟡 注意] 网络接口 ens2f1np1 处于 DOWN 状态
3. [🟡 注意] systemd-networkd-wait-online.service 失败
4. [🟡 注意] GPU 2 满载运行 (100% utilization, 101.74W)
5. [🟢 正常] CPU 负载虽高但 idle 91%，per-core 负载约 0.12 (正常范围)
6. [🟢 正常] 内存使用 14%，可用 217GB
7. [🟢 正常] 系统盘 53%，数据盘 41%，JuiceFS 1%
8. [🟢 正常] JuiceFS 无对象存储错误，transaction 延迟 P99 约 0.5ms
9. [🟢 正常] 文件句柄使用率 1.1% (23872/2097152)
10. [🟢 正常] 无 OOM/磁盘 IO 异常

---

> 由 ProAgent SRE Agent 自动生成。本巡检为只读操作，未执行任何系统变更。
