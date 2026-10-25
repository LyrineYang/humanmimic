# 实验与检查记录

只追加已经发生的结果。用 `null` 表示未知；没有运行的指标不填写为零。完整运行输出存到 `runs/<run_id>/`，本文件只保留摘要与位置。

| 日期与时区 | 检查 | 观察结果 | 证据位置 | 对项目的影响 |
| --- | --- | --- | --- | --- |
| 2026-10-24 Asia/Shanghai | Mac 与远程访问预检 | Mac arm64，无本地 NVIDIA GPU；dsai_2 经跳板连接被关闭 | 原会话命令输出；`evidence/preflight-20261024.json` | GPU 功能未验证 |
| 2026-10-24 Asia/Shanghai | 固定上游源码与解析入口 | 提交 45c03fac；5 个 Python 入口 AST 解析通过；LFS 数据仍为指针 | 同上 | 只证明源码入口可读，不证明运行正确 |
| 2026-10-25 Asia/Shanghai | 资源信息更新 | 用户报告 4060、WSL、32GB 内存、Modal 30美元额度 | 当前对话用户回复 | 首选改为 4060 本地；余额与硬件可用性待验证 |
| 2026-10-25 Asia/Shanghai | 启动文档核查 | 6份Markdown与预算JSON的本地链接、代码围栏、预算合计、小时价格换算和四项目标覆盖检查通过 | 当前会话本地校验输出 | 文档可交付，不代表R1至R4运行验收通过 |
| 2026-10-25 Asia/Shanghai | 桌面项目迁移与代码差异核查 | 原7个启动文件搬迁时SHA256逐一相同；官方源码无已暂存或未暂存差异；桌面旧仓库保持原状态 | 本次会话迁移命令输出；UPSTREAM.json | 保留文档与纯官方依赖，后续转Codex远程控制 |

原预检JSON中的Mac路径是当时的历史位置。迁移到WSL后，第一条运行记录应产生新的目标环境证据，不能沿用旧路径作为当前运行位置。

## 每次运行的记录模板

```yaml
run_id: null
status: awaiting_verification
goal: R1 | R2 | R3 | R4
hypothesis: null
change: null
code_commit: null
dirty_diff_sha256: null
upstream_commits: {}
model_file_sha256: {}
environment_file: null
config_file: null
input_manifest_sha256: null
evaluation_version: null
seed: null
command: null
host_and_gpu: null
modal_app_id: null
modal_call_id: null
started_at: null
finished_at: null
metrics: {}
peak_gpu_memory_mib: null
wall_seconds: null
estimated_cost_usd: null
actual_cost_usd: null
cost_source: null
artifacts: []
failure: null
decision: keep | revert | refine
next_action: null
```

运行目录至少保存命令与配置、环境版本、输入清单、原始日志、指标 JSON 和录像路径。成本估计与平台实际计费分别记录；未计入的启动、构建或存储开销也要列出。失败试次保留索引，不重复编号覆盖原结果。
