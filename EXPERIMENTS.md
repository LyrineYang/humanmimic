# 实验与检查记录

只追加已经发生的结果。用 `null` 表示未知；没有运行的指标不填写为零。完整运行输出存到 `runs/<run_id>/`，本文件只保留摘要与位置。

| 日期与时区 | 检查 | 观察结果 | 证据位置 | 对项目的影响 |
| --- | --- | --- | --- | --- |
| 2026-10-24 Asia/Shanghai | Mac 与远程访问预检 | Mac arm64，无本地 NVIDIA GPU；dsai_2 经跳板连接被关闭 | 原会话命令输出；`evidence/preflight-20261024.json` | GPU 功能未验证 |
| 2026-10-24 Asia/Shanghai | 固定上游源码与解析入口 | 提交 45c03fac；5 个 Python 入口 AST 解析通过；LFS 数据仍为指针 | 同上 | 只证明源码入口可读，不证明运行正确 |
| 2026-10-25 Asia/Shanghai | 资源信息更新 | 用户报告 4060、WSL、32GB 内存、Modal 30美元额度 | 当前对话用户回复 | 首选改为 4060 本地；余额与硬件可用性待验证 |
| 2026-10-25 Asia/Shanghai | 启动文档核查 | 6份Markdown与预算JSON的本地链接、代码围栏、预算合计、小时价格换算和四项目标覆盖检查通过 | 当前会话本地校验输出 | 文档可交付，不代表R1至R4运行验收通过 |
| 2026-10-25 Asia/Shanghai | 桌面项目迁移与代码差异核查 | 原7个启动文件搬迁时SHA256逐一相同；官方源码无已暂存或未暂存差异；桌面旧仓库保持原状态 | 本次会话迁移命令输出；UPSTREAM.json | 保留文档与纯官方依赖，后续转Codex远程控制 |
| 2026-10-25 Asia/Shanghai | Git基线与聊天归属 | 初始提交f14be2b；当前聊天已归入humanoid-demo项目；官方main与固定子模块提交一致 | Git提交、远端ls-remote及项目工具返回 | 未切换执行主机，不代表Windows环境已连通 |
| 2026-10-25 Asia/Shanghai | 实现与运行进度复核 | 执行端仍为Darwin arm64；修改前Git工作区干净；无业务代码实现提交，无仿真、视频或相机运行结果 | 当前会话uname、Git日志与PLAN复核 | 明确区分源码准备、实现与运行验收；R1未完成 |

| 2026-10-26 Asia/Shanghai | Remote 连接与代理 shell 预检 | 实际命令确认主机 zhen、PowerShell 7.6.5、Windows 10.0.26200 与 Windows cwd；WSL/内存/磁盘/GPU 尚未返回，awaiting_verification；辅助脚本写入 declined，已请求改为直接只读命令 | `runs/preflight-20261026-remote/remote-command-evidence.json` | 远程聊天可达且代理当前从 Windows 发起命令；不证明 WSL 或仿真可用 |

| 2026-10-26 Asia/Shanghai | 预检等待原因确认 | 用户确认网络连接出现问题，需要等待；WSL、内存、磁盘、GPU 结果仍缺失，保持 awaiting_verification，不重复提交 | 当前用户回复；`runs/preflight-20261026-remote/provenance.json` | 网络恢复后检查同一远端回合，再继续尚缺的只读检查 |

| 2026-10-26 Asia/Shanghai | Windows/WSL/GPU 预检完成 | 检查 passed：Windows PowerShell agent；Ubuntu 24.04.4/WSL2；Linux 内存约 15GiB、可用 14GiB；两端 nvidia-smi 均识别 RTX 4060 Laptop GPU 8188MiB、驱动596.49；C盘余23.66GiB、D盘余164.76GiB。项目 Git 检查 failed（128），Linux home 项目不存在；仿真 awaiting_verification | `runs/preflight-20261026-remote/results.json`；`environment-command-evidence.json` | 可通过 WSL 子进程访问 GPU；尚未切换代理、部署依赖或验证仿真。初次权限错误与脚本审批超时已保留；无计费资源启动 |

| 2026-10-26 Asia/Shanghai | WSL 主仓库副本准备 | 本地 bundle 与12文件快照已生成，HEAD b60a877；第一次载荷传输截短已废弃，完整61052字符载荷已重发并要求SHA256核对；远端回合仍在进行，副本 awaiting_verification。agent 设置 needs_input（无工具接口且Codex界面自动化被禁止） | `runs/wsl-workcopy-20261026/expected-manifest.json` | 可以继续使用 Windows agent 调用 WSL；推荐布局调整未完成，不能宣称已切换 agent |

| 2026-10-26 Asia/Shanghai | 分段传输核对 | 16段小消息在远端工具输出中均与本地原文一致；传输 passed。远端确认接收，但尚未返回仓库创建/HEAD/12文件哈希结果，副本仍 awaiting_verification | `runs/wsl-workcopy-20261026/transport-audit.json`；远端回合01a1772d | 不需要用户手动复制文件；不能把传输成功当作工作副本创建成功 |

| 2026-10-26 Asia/Shanghai | WSL 主仓库副本还原与验证 | passed：Ubuntu 本地 bundle clone 成功，HEAD b60a877 与12文件快照哈希一致，4份未提交文档修改保留；git fsck退出0，临时origin移除，SONIC固定45c03fac但未初始化实体。agent设置仍needs_input | `runs/wsl-workcopy-20261026/results.json`、`remote-command-evidence.json` | 文件准备已代办；Windows应用agent选择器、重启和添加项目需用户操作。未安装依赖、启动仿真或计费资源 |

| 2026-10-26 Asia/Shanghai | R1 部署准备状态复核 | 用户暂不能切换应用设置，沿用已验证的 Windows agent→WSL 调用方式。硬件预检与主仓库副本 passed；SONIC 子模块实体、依赖、权重、参考动作及验收工具尚未部署，无10秒或完整动作仿真结果，R1 awaiting_verification | 现有预检与副本结果；PLAN.md、STARTUP_PROMPT.md | 可以开始 R1 部署，尚不能直接运行验收；应用开关不作为阻碍。本轮仅核查和同步文档，未启动安装、下载或仿真 |

| 2026-10-27 Asia/Shanghai | WSL agent 切换后的登录故障登记 | 用户报告重启后 token exchange failed；代理/端口、证书、OAuth 错误待区分，未取得远端新命令证据，awaiting_verification | 当前用户回复；本机主机/项目列表查询 | WSL agent 切换非 R1 必需；不盲改代理或复制/删除认证文件，优先诊断与恢复原可用路径 |

| 2026-10-27 Asia/Shanghai | 登录错误细化 | 用户确认 token exchange failed 后续为 error sending request／连接超时或拒绝；优先查网络与代理可达性，尚无 Windows/WSL 对照命令结果，仍 awaiting_verification | 当前用户错误说明 | 不把代理假设当结论；不修改凭据或关闭证书验证，先取得对照结果再做条件修复 |

| 2026-10-28 Asia/Shanghai | 新 Remote 连接与 handoff 条件核对 | 新连接 env_e_6ae1ab32… 已出现在聊天列表；远端测试聊天 completed，Linux 格式 cwd；原生 WSL 为用户报告，尚无本轮 uname/GPU 输出。应用项目列表无远端 humanoid-demo，handoff awaiting_verification | list_threads/list_projects/read_thread；测试聊天01a1818b-6d19-79b0-99e0-efa404d3f60d | 改为优先 handoff 单聊天直接执行；不重复通过消息搬运文件或启动检查任务，先登记匹配 Git 项目 |

| 2026-10-28 Asia/Shanghai | 原生 WSL 与 Git 项目登记能力复核 | Bash/Ubuntu WSL2 实测确认；现有仓库 HEAD 与本地同为 b60a877，fsck通过。远端应用只登记 chat，缺少添加项目接口，新聊天未创建，登记 needs_input。普通沙箱因缺bwrap失败，获批只读命令成功；沙箱仍未修复 | `runs/handoff-preflight-20261028/results.json`；远端回合01a18195 | 仓库已在磁盘，不需重建或复制.git；用户需在远端应用添加既有文件夹，之后才能按项目创建聊天和检查handoff目标 |

| 2026-10-28 Asia/Shanghai | Linux/Windows 路径重新核验 | 实测 WSL Git 仓库存在，wslpath生成Ubuntu UNC地址；新登记桌面项目humanoid-demo-remote存在但Git退出128。用户界面找不到用户目录，UI可浏览性未验证 | `runs/handoff-preflight-20261028/path-recheck.json` | 区分WSL Git副本、Windows桌面日志目录和应用文件选择器；不再把三者地址混用 |

| 2026-10-28 Asia/Shanghai | 用户新建远端 Git 项目与引用聊天确认 | 项目登记 passed：c86526a2…，Linux路径正确，应用isGitRepository=true；引用聊天实际在该目录读取PLAN成功，但普通沙箱缺bwrap且当时等待审批。官方跨主机handoff文档已读取，实际UI入口与匹配仍awaiting_verification | `runs/handoff-preflight-20261028/project-registration.json` | 不再要求重新登记/复制项目；不把官方文档描述当作当前客户端入口实测，handoff尚未执行 |

| 2026-10-28 Asia/Shanghai | 原聊天跨主机 handoff 实际调用 | failed：工具返回 No matching saved project was found on zhen；没有 operationId，随后 read_thread 确认原聊天仍 local/idle。本地 main、HEAD b60a877、六份未提交文档修改已记录；git remote -v 为空。安装版应用匹配逻辑要求两端可解析的同一 Git origin 与相同子目录 | `runs/handoff-attempt-20261028/results.json`、`matching-rule-evidence.txt`、`source-before-recording.patch` | needs_input：确认真实 Git 远端 URL 或授权创建私有仓库后配置两端并重试；未迁移、未部署或启动仿真，未启动计费计算 |

| 2026-10-28 Asia/Shanghai | 私有 GitHub 仓库创建与发布准备 | 用户明确授权；浏览器创建 LyrineYang/humanoid-demo 成功，页面标记 Private。待提交的12个普通文件未发现常见凭据格式，SONIC只保存gitlink；本机gh未登录，已启动设备授权，首次推送needs_input，远端认证尚未核对 | `runs/github-publish-20261028/private-repository.png`、`results.json` | 整理本地提交并配置真实origin；用户完成CLI授权后推送，随后检查远端origin与私有仓库访问，再验证handoff |

| 2026-10-28 Asia/Shanghai | 首次私有仓库推送完成 | passed：用户完成GitHub设备验证，本机gh登录LyrineYang；提交7042ef2推送main并建立origin/main跟踪；gh repo view确认isPrivate=true。远端环境配置正在进行，新增文件尚未合并，不执行覆盖式同步 | `runs/github-publish-20261028/results.json` | 继续核对远端origin与认证；本聊天仍在Mac，handoff未完成 |

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
