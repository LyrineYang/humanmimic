# 人形机器人动作复刻项目启动资料

目标是在仿真中完成参考动作执行、实际视频复刻和实时相机遥操作，再验证场景约束动作修正。共用 G1、MuJoCo 和 SONIC，实时与录制视频共用 GEM-X。

当前资源方案为 RTX 4060 笔记本、WSL、32GB 系统内存，Modal 已有额度作为离线任务的补充。硬件是否足够由目标机器上的预检决定。

## 如何启动

1. 桌面项目已建立在 `/Users/nianzhen/Desktop/humanoid-demo`。本轮只迁移资料、保存未修改的官方依赖并建立 Git 基线，不在 Mac 开始部署或改机器人代码。
2. 可以沿用 Windows 原生代理，通过 `wsl.exe --cd /home/lyrine/projects/humanoid-demo --exec ...` 执行 Linux 命令。主要做 Linux/CUDA 开发时，推荐将应用代理切换为 WSL 并重启；这不是部署前的硬性门槛。只把集成终端改为 WSL 不等于改变代理执行环境。
3. 按 [远程协作说明](REMOTE_WORK.md) 连接 Windows 主机。执行项目在 WSL 内，例如 `~/projects/humanoid-demo`；同账号登录不会自动复制项目文件或把本聊天切换到另一台机器。
4. 在实际执行端读取 [PLAN.md](PLAN.md)，使用 [STARTUP_PROMPT.md](STARTUP_PROMPT.md)。需要持久执行时，再由用户激活其中的 `/goal`。
5. 代理负责依赖、实现与验证。人负责一次性配对主机、开放项目和短时摄像头配合。

## 文档职责

| 文件 | 只维护什么 |
| --- | --- |
| [STARTUP_PROMPT.md](STARTUP_PROMPT.md) | 启动指令和可激活的 Goal |
| [PLAN.md](PLAN.md) | 范围、验收、当前状态和下一步 |
| [EXPERIMENTS.md](EXPERIMENTS.md) | 已发生的检查和实验索引 |
| [RESOURCES.md](RESOURCES.md) | 4060 与 Modal 的部署分工、价格依据和预算 |
| [AGENTS.md](AGENTS.md) | 稳定的执行与维护规则 |
| [configs/budget.json](configs/budget.json) | 预算和价格计算输入 |
| [REMOTE_WORK.md](REMOTE_WORK.md) | Windows WSL 与跨设备协作步骤 |

官方精简源码位于 `vendor/GR00T-WholeBodyControl`，以 Git 子模块固定版本，未下载模型与完整 LFS 资产。私有 Git 远端已建立并完成首次推送：[LyrineYang/humanoid-demo](https://github.com/LyrineYang/humanoid-demo)。两端使用同一 origin，远端认证和 handoff 结果以 [远程协作说明](REMOTE_WORK.md) 与 [当前计划](PLAN.md) 为准。R1–R4 尚未通过运行验收。

## 方法参考

采用明确假设、固定对照、实验记录和保留或撤回修改的工作方式；不照搬长时间无约束搜索。

- [OpenAI 蛋白折叠架构探索案例](https://learn.chatgpt.com/use-cases/discover-protein-folding-architectures)
- [OpenAI Goal 编写指南](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex#how-to-write-a-goal)
