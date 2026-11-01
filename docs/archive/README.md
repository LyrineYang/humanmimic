# 历史交接文档索引

这些文档是不可变Git提交中的原文快照，仅用于审计和理解当时决策，**不是当前运行指令**。现行入口为[STARTUP_PROMPT](../../STARTUP_PROMPT.md)、[PLAN](../../PLAN.md)、[HANDOFF](../../HANDOFF.md)、[REMOTE_WORK](../../REMOTE_WORK.md)和[RESOURCES](../../RESOURCES.md)。

归档基准提交：`a8a58e6c6b7aaac36ad530a2b6682ef778e936fe`。历史正文没有名称替换、重排或哈希更新；原始运行路径、旧仓库名、早期失败/部署状态和估计保持原貌。链接使用改名后的同一仓库定位原Git对象。

| 原文 | 内容时段与用途 | 原文SHA256 |
| --- | --- | --- |
| [STARTUP_PROMPT.md](https://github.com/LyrineYang/humanmimic/blob/a8a58e6c6b7aaac36ad530a2b6682ef778e936fe/STARTUP_PROMPT.md) | 旧Mac/Windows提示、R2 Goal与追加记录；其中推进R2的命令已失效 | `3408f3e77d7ff6303f593c907059fed8ea7cc083ca70f1ad1ba403d393de1f86` |
| [REMOTE_WORK.md](https://github.com/LyrineYang/humanmimic/blob/a8a58e6c6b7aaac36ad530a2b6682ef778e936fe/REMOTE_WORK.md) | 早期连接、目录不存在、初次部署与同步记录；不代表当前部署状态 | `ed9f76f7108bc6115a2f6a2c9af43838e75ffad3965c3fd438a8e9d7890be38b` |
| [RESOURCES.md](https://github.com/LyrineYang/humanmimic/blob/a8a58e6c6b7aaac36ad530a2b6682ef778e936fe/RESOURCES.md) | 2026-10-25至11-01旧价格/估计及收尾；旧估计不作为当前预算 | `8192919139ec8aa4e5cda5c460a4840ba5dbf98e23acb7c9e6d38789f8d5f64e` |
| [HANDOFF.md](https://github.com/LyrineYang/humanmimic/blob/a8a58e6c6b7aaac36ad530a2b6682ef778e936fe/HANDOFF.md) | 修订前交接快照；对应此前交接证据的文件哈希，旧URL仍保留 | `283290a4c326a76255c6b6c12e44c63f8ec5aabe129f2dff69e438a4f72acf6c` |

本地完整Git历史也可只读查看，例如：

```bash
git show a8a58e6c6b7aaac36ad530a2b6682ef778e936fe:STARTUP_PROMPT.md
```

旧的[EXPERIMENTS](../../EXPERIMENTS.md)、`evidence/`、`configs/`及原始`runs/`没有因仓库改名被重写。源码/冻结资产的校验仍使用原记录；新文档的哈希单独记录在本次交接修订证据中。

[operations.zh-CN.md](../operations.zh-CN.md)是此前已有的中文README历史归档，本次不改其内容；其中旧设备路径、旧仓库名和阶段状态不属于现行接手指令。
