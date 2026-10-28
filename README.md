# 人形机器人动作复刻项目启动资料

目标是在仿真中完成参考动作执行、实际视频复刻和实时相机遥操作，再验证场景约束动作修正。共用 G1、MuJoCo 和 SONIC，实时与录制视频共用 GEM-X。

当前资源方案为 RTX 4060 笔记本、WSL、32GB 系统内存，Modal 已有额度作为离线任务的补充。硬件是否足够由目标机器上的预检决定。

## 如何启动

1. 当前执行项目为 Windows 主机 zhen 的 WSL 目录 `/home/lyrine/projects/humanoid-demo`。2026-10-28 已实测代理直接在 WSL 执行，Git 工作副本、GPU 枚举和 CUDA 驱动初始化检查通过；Mac 路径仅保留为历史记录。
2. WSL 代理执行位置已经确认。运行依赖、图形、现场相机和物理控制仍需各自检查，不能用 WSL 或 GPU 可见性替代功能验收。
3. 按 [远程协作说明](REMOTE_WORK.md) 连接 Windows 主机。执行项目在 WSL 内，例如 `~/projects/humanoid-demo`；同账号登录不会自动复制项目文件或把本聊天切换到另一台机器。
4. 在实际执行端读取 [PLAN.md](PLAN.md)，使用 [STARTUP_PROMPT.md](STARTUP_PROMPT.md)。需要持久执行时，再由用户激活其中的 `/goal`。
5. 代理负责依赖、实现与验证。人负责一次性配对主机、开放项目和短时摄像头配合。

私有项目仓库：[LyrineYang/humanoid-demo](https://github.com/LyrineYang/humanoid-demo)。源码与配置由 Git 同步，环境和运行资产按下文单独准备。

## R1 的 conda 环境

用户于 2026-10-28 指定使用 conda。已配置 WSL Linux 文件系统内的项目级 Miniforge，独立环境名 `humanoid-r1`；Python 3.10 跟随固定版官方 MuJoCo 安装脚本。基础工具由 conda-forge 管理，官方 Python 包及 CUDA 版 PyTorch 通过环境内 pip 安装。配置为 [environment-r1.yml](configs/environment-r1.yml)、[constraints-r1.txt](configs/constraints-r1.txt) 和 [pip 版本锁定文件](configs/requirements-r1.lock.txt)。

在 WSL Bash 中激活：

```bash
cd /home/lyrine/projects/humanoid-demo
source scripts/activate-r1.sh
```

激活后可正常使用 `conda`、`python`、`pip`；环境位于 `.local/miniforge3/envs/humanoid-r1`。Miniforge 未修改 `~/.bashrc`，系统 Python 与驱动保持原状。激活脚本设置 `CYCLONEDDS_HOME`，并默认选择 EGL 离屏渲染；需要图形窗口时另行验证 WSLg。

完整 R1 环境已补齐 TensorRT 10.13.3.9、CUDA 开发工具 12.8.93、ONNX Runtime C++ 1.22.0，官方 C++ 控制器已编译。激活脚本设置原生库路径：TensorRT 位于 `.local/tensorrt-10.13.3`，ONNX Runtime 位于 `.local/onnxruntime-linux-x64-1.22.0`。

Unitree SDK 固定要求 CycloneDDS Python 0.10.2，当前采用源码构建的绑定；运行时通过 `.local/unitree-dds` 使用 SDK 配套 C/C++ 库。不要用普通 pip wheel 替换：本次 wheel 实际内置 C 0.11.0，会绕过 `CYCLONEDDS_HOME`。初步配置时自行构建的 C 库留作历史产物，不是当前运行库。DDS 使用 [r1-dds.xml](configs/r1-dds.xml) 的 lo 单播和小包分片，解决本机大 UDP 数据报丢失；系统网络与驱动未改动。完整证据在 `runs/r1-full-setup-20261028/`。

环境冒烟检查使用新的结果目录，避免覆盖既有结果：

```bash
python scripts/check-r1-environment.py --output "runs/r1-env-$(date +%Y%m%d-%H%M%S)"
```

上述组件检查与 `pip check` 已通过；它本身不执行策略。随后完整 SONIC→MuJoCo 物理复现也已通过一次，见下方结果。离屏录像使用 Mesa llvmpipe 软件渲染，GPU 图形加速和图形窗口尚未验证。当前状态以 [PLAN.md](PLAN.md) 为准。

## R1 结果与复跑

已完整执行官方样例 `macarena_001__A545`：1375 帧、27.5 秒，29 关节 RMSE 0.13617 rad，未跌倒，播放期间弹力带关闭。控制器通过 TensorRT 在 RTX 4060 上推理，MuJoCo 保持自由根部、重力与接触；录像由执行结束后记录的真实状态生成。

- [结果报告](runs/r1-reproduction-20261028-01/REPORT.md)
- [完整录像](runs/r1-reproduction-20261028-01/actual-execution.mp4)
- [全部控制样本指标](runs/r1-reproduction-20261028-01/full-sample-metrics.json)
- [完整环境版本与结果](runs/r1-full-setup-20261028/results.json)

复跑时选择尚不存在的新结果目录：

```bash
source scripts/activate-r1.sh
python scripts/run-r1-reproduction.py --output runs/r1-new-reproduction
python scripts/summarize-r1.py --run runs/r1-new-reproduction
```

脚本会保存原始配置、版本/权重校验、实际状态、参考值、失败判定和录像；`summarize-r1.py` 用完整原生 CSV 复核所有帧，并校验视频。前四轮预检和失败证据均保留。当前仅完成一次完整动作，原计划五动作各两次的 R1 整体验收仍为 awaiting_verification。

需要增量重编译现有控制器时，保持 RUNPATH 设置，避免 conda 的旧式 RPATH 覆盖 SDK 配套 DDS 库：

```bash
source scripts/activate-r1.sh
cmake -S vendor/GR00T-WholeBodyControl/gear_sonic_deploy -B .local/build/sonic-deploy -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
  -DTENSORRT_LIBRARY_DIR="$TensorRT_ROOT/lib" \
  -DCMAKE_EXE_LINKER_FLAGS=-Wl,--enable-new-dtags -DBUILD_EXAMPLES=OFF
cmake --build .local/build/sonic-deploy --target g1_deploy_onnx_ref --parallel 2
```

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

官方源码以 Git 子模块固定版本，路径为 `vendor/GR00T-WholeBodyControl`；本机完整环境与一次闭环复现已通过。局部仿真 DDS 配置补丁见 [UPSTREAM.json](UPSTREAM.json) 和 [补丁文件](patches/sonic-loopback-dds.patch)，策略、增益和动作逻辑保持官方版本。原计划的 R1 整体验收与 R2–R4 仍待完成。运行资产、环境及 runs 不提交 Git。

## 方法参考

采用明确假设、固定对照、实验记录和保留或撤回修改的工作方式；不照搬长时间无约束搜索。

- [OpenAI 蛋白折叠架构探索案例](https://learn.chatgpt.com/use-cases/discover-protein-folding-architectures)
- [OpenAI Goal 编写指南](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex#how-to-write-a-goal)
