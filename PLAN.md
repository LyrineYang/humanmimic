# 人形机器人复现与场景动作修正计划

## 交付范围

先完成三个共用底座的复现，再完成一个能比较效果的自研模块。项目不以源码安装成功、参考姿态动画或一次演示替代物理控制验证。

| 编号 | 动作来源与路径 | 实现进度 | 运行验收 |
| --- | --- | --- | --- |
| R1 | 少量 G1 数据集动作 → SONIC → MuJoCo | 远端硬件预检与 WSL 主仓库副本完成；SONIC 子模块实体、环境、资产和验收工具未部署 | 未运行；awaiting_verification |
| R2 | 实际视频 → GEM-X → SOMA 转 SMPL → 缓存回放 → SONIC | 官方桥接源码已准备；模型与链路未集成 | 未运行；awaiting_verification |
| R3 | 现场摄像头 → 同一动作转换与流式接口 → SONIC | 尚未接入相机 | 未运行；needs_input |
| R4 | 原始参考动作与障碍物几何 → 自研动作修正 → SONIC | 自研模块尚未编写 | 未运行；awaiting_verification |

当前一句话进度：远端硬件预检和 WSL 主仓库副本已完成；SONIC 子模块实体、依赖、权重、参考动作和验收工具仍未部署，尚无仿真运行结果。远端已登记 Git 项目 `/home/lyrine/projects/humanoid-demo`。2026-10-28 实际 handoff 因没有匹配项目失败；安装版应用以两端 Git origin 的仓库标识及相同仓库子目录匹配，同名目录和相同 HEAD 不足以匹配。用户现已明确授权创建私有 GitHub 仓库并推送本项目；已创建 `https://github.com/LyrineYang/humanoid-demo`，浏览器确认 Private。本机 CLI 已登录正确账号；本地提交 `7042ef2` 已推送到私有仓库 main（`passed`），origin 已配置。远端 GitHub 认证与 origin 配置尚未复核，handoff 尚未成功。远端聊天正在按用户另一项请求配置 R1 conda 环境，已有新增配置与脚本，禁止用拉取或重置覆盖这些改动；远端后续运行证据以该聊天为准。证据：`runs/handoff-attempt-20261028/`、`runs/github-publish-20261028/`。

## 验收与数据划分

下面是本项目的工程门槛，不是论文报告的性能。若样例揭示门槛定义本身有误，先说明证据并取得用户同意再修改；不能看过保留测试结果后放宽门槛。

### R1 参考动作物理执行

- 固定 5 段动作，至少覆盖上肢、躯干或下肢两类，先选舞蹈手势、Macarena、深蹲等较易片段。
- 每段完整执行两次；至少 4 段两次均满足未跌倒、未触发跟踪失败，并且关节跟踪 RMSE 不超过 0.35 rad。关节顺序、有效关节集合和角度差算法预先写入评估配置。
- 关节 RMSE 使用控制器实际状态与同一时刻参考值计算，不把目标值当成实际值。保持重力、接触、自由根部和控制器启用，不逐帧写机器人状态。
- 保存实际状态、参考值、失败判定、所有试次结果与至少一段完整录像。

### R2 实际视频复刻

- 准备 5 段调试视频与 5 段保留测试视频，覆盖至少 3 类动作。视频提取使用该视频本身；不以动作检索或已知数据集动作替换提取结果。
- 先限定单人、固定相机、全身及脚部可见、平地。第一版主要还原姿态与节奏；真实世界绝对移动轨迹是后续扩展。
- 保留测试前冻结提取、转换、平滑、时序和评估规则。至少 4/5 测试视频完整提取并稳定完成仿真复刻。
- 在测试清单中为每条视频定义关键动作事件，例如抬左手、下蹲再起身、左右交替。事件方向正确、顺序一致，且有原视频、提取骨架、实际执行三路对照。
- 记录相对提取参考的身体误差和时间偏移；单目提取结果不是人体三维真值，不能据此声称真实人体绝对误差。

### R3 实时相机遥操作

- 现场连续运行至少 3 分钟，完成 3 类预定低速动作，且没有跌倒或输入失控。
- 感知有效输出平均至少 10Hz，控制目标为 50Hz，测得控制周期 P95 不超过 30ms。记录真实输入更新时间，不能把控制频率当成视觉帧率。
- 明确测试相机短暂遮挡或断流与恢复；记录系统行为，不能让旧帧无限排队。
- 测量端到端延迟。首次验收以稳定性和正确复刻为主，延迟作为独立指标；后续优化目标为 P95 ≤300ms，不能把前视长度当实测延迟。
- 录像文件回放只用于预检，不能替代现场摄像头。缺少现场输入时保持 needs_input，并继续其他目标。

### R4 场景约束动作修正

- 第一版限定基本固定双脚的单臂伸手、一个静态箱体、仿真已知几何。修改参考动作，由原控制器执行，不修改机器人实际状态。
- 用腕部路径控制点生成候选，经逆运动学和碰撞距离筛选，再用实际 SONIC 与 MuJoCo 的闭环回放选优。搜索先离线运行。
- 对照包含原动作、仅缩小幅度、自研完整方法；消融去掉闭环回放筛选。输入、策略和场景保持一致。
- 开发使用 10 个布局；另冻结至少 20 个未调试布局并完整评测。冻结布局列表、随机种子、碰撞判据、稳定性判据、目标完成条件和动作偏差指标。
- 至少在 3 个保留布局中，原动作碰撞而修正动作在实际物理执行中无碰撞、稳定达到同一伸手目标。全体布局同时报告任务成功率、碰撞率、动作偏差和计算时间；不能仅展示挑选成功的视频。
- 以成功到达目标和保持动作特征排除“完全不动”解。给出至少 3 组对照录像。若改进未出现，记录否定结果并继续可行修复；不能把实现完代码等同于目标通过，也不宣称论文级首创。

## 当前状态

更新于 2026-10-28，Asia/Shanghai。

- 2026-10-28 用户新建项目与聊天确认 `passed`：远端项目ID `c86526a2-65b2-400a-aa10-5dc35f391b01`，路径 `/home/lyrine/projects/humanoid-demo`，应用识别为 Git 仓库；引用聊天“报告远程测试项目与环境”（01a181c4-049a-7823-9890-8f3cdd112550）的实际 Bash 命令在该目录读取 PLAN 成功。该聊天当时 active/waitingOnApproval，普通命令先因缺 bwrap 退出101；未安装修复。远端 PLAN 仍为10月26日快照，本地后续更新未自动同步。官方文档与 What's New 均描述跨主机 chat handoff，但这不能证明当前 UI 一定显示入口或已匹配目的地；用户正在核对，当前未迁移运行位置。证据 `runs/handoff-preflight-20261028/project-registration.json`。

- 2026-10-28 路径重新核验：实际命令确认主仓库在 Ubuntu 的 `/home/lyrine/projects/humanoid-demo`，`wslpath -w` 返回 `\\wsl.localhost\Ubuntu\home\lyrine\projects\humanoid-demo`。新登记的应用项目 humanoid-demo-remote 指向 `/mnt/c/Users/Oscar/Desktop/humanoid-demo-remote`，该桌面目录存在但不是 Git 仓库；这是不同目录，不能混称为已准备的 Git 副本。`/mnt/c/Users/Oscar` 在远端命令环境存在，但用户报告界面不可见；本轮没有验证该界面的可浏览性，不能用命令存在性代替 UI 验证。证据 `runs/handoff-preflight-20261028/path-recheck.json`。

- 2026-10-28 handoff 准备复核：已从新远端直接运行 `/bin/bash` 命令，确认 Ubuntu/WSL2、现有 `/home/lyrine/projects/humanoid-demo`、HEAD b60a877 与本地相同，git fsck 退出0；远端保留4份未提交文档，本地后续修改未自动同步。两端均没有添加既有应用项目的工具接口，远端应用当前只登记非Git项目 chat。因此本轮未登记 humanoid-demo、未创建新聊天、未执行 handoff；需要用户在远端应用添加既有文件夹一次。另发现原生 Linux 沙箱缺少 bwrap，普通命令退出101，自动批准的只读命令在沙箱外成功；沙箱依赖仍待修复，未安装或降低安全设置。原始证据：`runs/handoff-preflight-20261028/results.json`。

- 2026-10-28 新连接核对：新主机 identity 为 `remote-control:env_e_6ae1ab32b07c8331990e55255681166e`，与旧连接不同；远端聊天“Clarify test request”已 completed，无错误，cwd `/mnt/c/users/oscar/desktop/chat`。用户报告原生 WSL 已启用，当前仅有 Linux 路径元数据及成功对话证据，尚未重新执行 uname/GPU 检查。应用项目列表当前没有返回远端 humanoid-demo；原 `/home/lyrine/projects/humanoid-demo` 副本本轮未重新检查存在性。handoff 尚未执行，也未创建或消息驱动新的远端检查任务。下一步在 Windows 应用登记该 Linux Git 项目，确认当前聊天运行位置菜单中出现匹配目标；当前聊天需用户从界面 handoff。

- 2026-10-27 登录排查 `awaiting_verification`：用户报告切换 WSL agent 后浏览器登录环节 token exchange failed，后续错误为 error sending request／连接超时或拒绝。优先排查令牌请求的网络、代理地址和监听端口；WSL NAT localhost 代理不可达只是待验证假设，未确认根因。本机当前项目与聊天列表未列出 zhen，无法直接取得新远端命令证据。需对照 Windows/WSL 的认证域名连通性、WSL 默认代理与直连结果；未修改代理、凭据或 WSL 网络配置，未宣称修复。

- 2026-10-26 远端环境检查 `passed`（仅指本次检查已完成）：实际确认 `zhen` 为 Windows 11 家庭版，代理命令使用 PowerShell 7.6.5，cwd 为 `C:\Users\Oscar\Desktop\humanoid-demo-remote`；代理尚未切换到 WSL。WSL 3.0.3.0，默认 Ubuntu 24.04.4 LTS、WSL2，Linux 可见约 15 GiB 内存、可用约 14 GiB、Swap 4 GiB。Windows 与 WSL 的 nvidia-smi 都识别 RTX 4060 Laptop GPU（8188 MiB），驱动 596.49。C 盘剩余约 23.66 GiB，D 盘约 164.76 GiB。当前远端目录不是 Git 仓库，`/home/lyrine/projects/humanoid-demo` 不存在；部署尚未就绪。原始输出和检查结果见 `runs/preflight-20261026-remote/environment-command-evidence.json`、`results.json`。未修改代理设置，未安装依赖或启动仿真；R1–R4 仍未通过运行验收。

- 用户资源：RTX 4060 笔记本，32GB 内存，已完成上述 Windows/WSL/GPU 只读预检；相机、图形显示和框架 CUDA 尚未测试。
- 当前执行端仍是 Mac。2026-10-24 已检出官方 SONIC 精简源码，固定提交 `45c03facbf848e0c743091b7d9c17952096ff908`，并对 5 个相关 Python 入口进行 AST 语法解析，均通过。
- 桌面项目现位于 `/Users/nianzhen/Desktop/humanoid-demo`，官方源码迁入 `vendor/GR00T-WholeBodyControl` 并以子模块固定原提交。该目录不包含完整 LFS 实体，不能直接当成完整安装。历史预检保存于 `evidence/preflight-20261024.json`。
- 桌面旧仓库未修改。2026-10-24 的 dsai_2 SSH 预检被跳板端关闭，尚未重测；当前首选已经转为用户的 4060。
- 用户报告 Modal 有 30 美元额度；未读取账户余额，未启动计费任务。本次只准备启动资料，当前没有活跃 Goal 或自动化。
- 2026-10-25 用户要求后续通过 Codex 远程控制协作。本轮停止实现推进；核对官方源码没有已暂存或未暂存的业务代码修改，无需对它执行 reset。仅迁移文档、固定依赖和初始化项目 Git。
- 聊天“调研人形机器人视频动作复刻”已关联桌面项目 humanoid-demo。2026-10-26 已验证 Mac 能控制 Windows 主机 zhen 的执行聊天；Mac 本地聊天仍在 Mac 执行。跨主机 Handoff 尚未进行，远端 Git 项目仍需准备。
- 已核对官方main仍为 `45c03facbf848e0c743091b7d9c17952096ff908`，迁入的子模块与之相同。旧桌面仓库除未跟踪AGENTS.md外工作区干净，无本地独有分支提交，但存在一条stash；删除旧目录前须确认新项目 `.local/legacy-sonic/` 的恢复包与AGENTS.md备份已验证。恢复包不提交Git。

本次环境检查期间曾因网络问题等待、辅助脚本写入审批超时；随后同一远端回合改用直接命令，已取得所需输出。初次受限调用的 CIM/WSL 状态查询报权限错误，后续调用成功；最后 Linux 合并命令返回 128 来自 Git 目录检查失败，不能误报为 WSL 或 GPU 失败。当前仿真部署与运行仍为 `awaiting_verification`。

## 下一步

2026-10-26 设置调整请求：WSL 主仓库副本已建立于 `/home/lyrine/projects/humanoid-demo`，状态 `passed`。Git HEAD `b60a87778838f35c0bb771a29991cb4ede685bb7`、12 个跟踪文件的传输快照 SHA256 与本地预期逐一相同；4 份未提交文档修改已保留，`git fsck --no-reflogs` 通过，临时 bundle 的 origin 已移除。SONIC 子模块固定提交已核对但实体未下载；这不是部署完成。预期清单、原始命令与结果在 `runs/wsl-workcopy-20261026/`。当前工具没有应用 agent 设置接口，且禁止 Computer Use 操作 Codex；应用切换、重启及添加 WSL 项目为 `needs_input`，需要用户在 Windows 端操作。两步均是推荐配置，不是仿真硬性前提；现有 Windows agent 调用 WSL 的路径仍可使用。

传输记录：长消息曾截断，已弃用；16 段小消息逐段核对后，远端完成长度、字节数和整体 SHA256 校验并还原仓库。副本对应传输时快照；本轮后续 Mac 文档更新不声称已实时同步。Windows 添加项目路径为 `\\wsl.localhost\Ubuntu\home\lyrine\projects\humanoid-demo`。用户重启应用前先确认远端聊天已结束，重启后需重新验证原生命令环境，不能把已有 WSL 子进程当作 agent 已切换的证据。

1. 远程配对和 Windows/WSL/GPU 只读预检已完成。下一次部署先处理远端 Git 工作副本、C 盘空间，并选用现有 Windows agent 调用 WSL 或推荐的 WSL agent；切换不是硬性门槛。若修改设置，重新核对原生命令环境、工作目录与 GPU，再检查图形和相机路径；Mac 端不部署仿真。
   用户最新约束：暂不更改应用设置。R1 的 Linux 命令可经 `wsl.exe --cd /home/lyrine/projects/humanoid-demo --exec ...` 执行；显式指定目录和 Linux 可执行程序，不能误用 Windows Python。现有日志证明这一调用方式可用，但不证明框架 CUDA 或 SONIC 已运行。
2. 获取固定版源码、匹配权重、最少参考动作和 LFS 实体；创建独立环境，不运行会删除已有环境的安装步骤。
3. R1 的 10 秒预检 → 单个完整动作 → 五动作验收。预检通过后才扩大下载和评测。
4. GEM-X 单独视频推理 → 缓存流式回放 → 与控制并行测显存；推进 R2，再现场验收 R3。
5. 用已经通过的参考动作开始 R4。任何现场等待期间继续独立开发与离线验证。

## 后续研究

2026-10-26 最终复查：远端工作副本回合 `01a1772d-8389-7a72-8bbf-18bbee70c981` 已 completed，聊天 idle，无错误；该任务不再占用运行回合。应用 WSL agent 切换仍未执行，需要用户在 Windows 应用中操作。

当前四项之后再考虑更小的控制器、预测补偿延迟、用世界模型加速候选评估。SuperMimic 完整训练复现、坐椅子、上台阶和视频场景重建均不在首轮额度内。
