# 人形机器人动作复刻项目启动资料

目标是在仿真中完成参考动作执行、实际视频复刻和实时相机遥操作，再验证场景约束动作修正。共用 G1、MuJoCo 和 SONIC，实时与录制视频共用 GEM-X。

当前执行方案为 RTX 4060 笔记本、WSL、32GB 系统内存，R2 使用D盘独立conda并串行运行。计费云资源当前未获授权，硬件是否足够以目标机器的实测为准。

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

脚本会保存原始配置、版本/权重校验、实际状态、参考值、失败判定和录像；`summarize-r1.py` 用完整原生 CSV 复核所有帧，并校验视频。前四轮预检和失败证据均保留。以上为前阶段单动作基线；当前固定五动作各两次的整体验收已通过，见下方正式验收结果。

需要增量重编译现有控制器时，保持 RUNPATH 设置，避免 conda 的旧式 RPATH 覆盖 SDK 配套 DDS 库：

```bash
source scripts/activate-r1.sh
cmake -S vendor/GR00T-WholeBodyControl/gear_sonic_deploy -B .local/build/sonic-deploy -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" \
  -DTENSORRT_LIBRARY_DIR="$TensorRT_ROOT/lib" \
  -DCMAKE_EXE_LINKER_FLAGS=-Wl,--enable-new-dtags -DBUILD_EXAMPLES=OFF
cmake --build .local/build/sonic-deploy --target g1_deploy_onnx_ref --parallel 2
```

## R1 归档与固定复跑配置

已完成：项目内 conda 环境、原生推理依赖、官方控制器编译、WSL DDS 修复、完整 Macarena 物理执行及实际状态录像。可随 Git 同步的结果见 [基线摘要与产物哈希](evidence/r1-baseline-20261028.json)。上面的 `runs/` 报告和录像只存在于原执行机，克隆仓库不会获得它们。

以下为已用于正式验收、后续复跑保持不变的五动作清单，全部资产 SHA256 在 [r1-suite.json](configs/r1-suite.json)：

| 动作 | 类别 | 有效帧 / 时长 | 完整试次 |
| --- | --- | --- | --- |
| Macarena | 上肢手势 | 1375 / 27.50 s | 2 |
| Dance in da party | 全身舞蹈 | 497 / 9.94 s | 2 |
| Squat | 下肢深蹲 | 424 / 8.48 s | 2 |
| Walking quip 360 | 行走转向 | 455 / 9.10 s | 2 |
| Forward lunge（官方镜像样例） | 下肢弓步 | 399 / 7.98 s | 2 |

五个样例资产已在本机获取，并与固定上游 LFS 对象逐项核对。CSV 表头不计入帧数。两个原有 Macarena 演示/工具验证结果不替换本清单的固定试次；批次入口检测到任一既有试次或日志即拒绝重跑。全部十次都保留，至少四个动作的两次均满足原门槛才通过。它们属于官方样例/调试动作，不能称为未见保留测试。

准备工具只核对输入并生成命令，不启动控制器。每轮使用新目录：

```bash
source scripts/activate-r1.sh
python scripts/prepare-r1-suite.py --output runs/r1-suite-NEW
# 下一轮开始执行时运行；所有控制器串行使用同一 DDS domain。
bash runs/r1-suite-NEW/run-trials.sh
# 可单独复核，未完成返回 2，失败返回 1，通过返回 0。
python scripts/audit-r1-suite.py --suite runs/r1-suite-NEW
```

运行脚本新增 `--evaluation <冻结配置.json>`，默认仍用原 Macarena 配置。准备程序检查动作、固定策略、二进制、DDS 和补丁哈希；汇总程序核对全帧、相同评估规则、物理条件、策略/控制器版本及视频审计，报告全部十次。就绪检查通过只表示可以运行；当前一次完整正式批次已验收通过，后续复跑仍需独立审计。R1 后按计划接 GEM-X 视频链路（R2）。

新机器需单独重建环境。使用 [Linux conda 精确包清单](configs/conda-r1-linux-64.explicit.txt)、pip 锁定文件和 [原生依赖下载地址/校验清单](configs/r1-native-dependencies.json)；原生包仅解压到项目内，不安装系统驱动。先获取固定子模块，再应用补丁：

```bash
GIT_LFS_SKIP_SMUDGE=1 git submodule update --init
git -C vendor/GR00T-WholeBodyControl apply --check "$PWD/patches/sonic-loopback-dds.patch"
git -C vendor/GR00T-WholeBodyControl apply "$PWD/patches/sonic-loopback-dds.patch"
```

仅在新检出且尚未应用补丁时执行以上两条 apply。获取 G1 模型、x86_64 SDK 和清单中的五段动作 LFS 实体后，建立 `.local/unitree-dds/include` 与 `.local/unitree-dds-lib` 对应的 SDK 头文件/SONAME 链接，再构建 Python DDS 源码绑定与控制器。不同机器重新编译的二进制/运行库需重新记录和验收，不能冒用本机通过记录。大型模型、环境和原始 `runs/` 不随 Git 上传。

## 整批执行与中断恢复

首轮五动作双次运行已保留完整失败证据，见 [首轮摘要](evidence/r1-batch-20261029.json)。检查发现仿真使用逐步相对 sleep 时，物理时间仅为墙钟的 0.82–0.97，而参考动作仍按墙钟 50 Hz 播放。运行器现使用绝对截止时间节拍，物理步长、策略、增益和动作不变；[三项独立诊断](evidence/r1-pacing-repair-20261029.json)恢复约 1.000 实时比例并完整通过，诊断不替代正式验收。

当前统一驱动 617.42 的正式目录为 `runs/r1-suite-acceptance-20261029-03`，状态以 PLAN.md 和该目录 `suite-audit.json` 为准。原驱动 621.01 的中断批次不混入此轮。

本轮目录已包含执行前环境清单 `execution-manifest.json`，可使用检查点入口恢复：

```bash
source scripts/activate-r1.sh
python scripts/resume-r1-suite.py --suite runs/r1-suite-acceptance-20261029-03 --check-only
python scripts/resume-r1-suite.py --suite runs/r1-suite-acceptance-20261029-03
```

先看日志与活跃进程；有控制器运行时不要重复调用。入口校验 GPU/驱动、Python 包版本、冻结源码和权重；驱动改变时拒绝续测，需另建统一环境的完整批次。已成功的物理试次只补录像/审计，先保存中断录像；失败或中断的物理试次保留，不自动重跑替换。新批次仍可使用上面的准备工具和单次启动脚本；使用恢复入口前必须先记录执行环境清单。`--no-video` 只用于独立诊断，缺少完整录像与产物审计的运行不能通过整批验收。

## R1 正式整批验收结果

2026-10-29，固定五动作各两次全部通过：**10/10试次、5/5动作双次通过、6300个完整控制样本，无跌倒**。同一RTX4060 Laptop、驱动617.42，关节RMSE范围 **0.10875–0.17517 rad**，原门槛≤0.35。物理时间/墙钟比例0.99995–1.00005；十段实际状态录像和全量原生控制日志已独立审计。

- 可随Git同步：[完整验收摘要与产物SHA256](evidence/r1-acceptance-20261029.json)。
- 原执行机：[正式报告](runs/r1-suite-acceptance-20261029-03/REPORT.md)、[全部结果](runs/r1-suite-acceptance-20261029-03/results.json)、[十试次汇总](runs/r1-suite-acceptance-20261029-03/suite-audit.json)。
- [舞蹈完整实际轨迹录像](runs/r1-suite-acceptance-20261029-03/dance_in_da_party_001__A464-trial-01/actual-execution.mp4)。报告包含全部十段录像与原始数据链接。

首轮失败与第二轮中断均保留，没有以诊断或成功片段替换试次。此结论仅覆盖本机R1官方样例工程验收；GPU图形加速/窗口与现场相机未验收，R2–R4尚未完成。下一阶段按PLAN推进R2视频链路。模型、环境、原始轨迹和录像保持本机存储，新增云费用0美元。

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

官方源码以 Git 子模块固定版本，路径为 `vendor/GR00T-WholeBodyControl`；本机完整环境与一次闭环复现已通过。局部仿真 DDS 配置补丁见 [UPSTREAM.json](UPSTREAM.json) 和 [补丁文件](patches/sonic-loopback-dds.patch)，策略、增益和动作逻辑保持官方版本。R1整体验收已通过；R2–R4仍待完成。运行资产、环境及 runs 不提交 Git。

## 方法参考

采用明确假设、固定对照、实验记录和保留或撤回修改的工作方式；不照搬长时间无约束搜索。

- [OpenAI 蛋白折叠架构探索案例](https://learn.chatgpt.com/use-cases/discover-protein-folding-architectures)
- [OpenAI Goal 编写指南](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex#how-to-write-a-goal)


## R2 本机视频链路（当前预检中）

当前D盘独立conda/CUDA、固定GEM-X资产与SOMA/SMPL接口已检查通过；首条完整YouTube原片正在预检，物理/三路demo与5调试+5保留整批尚未验收。当前执行Goal统一保存在 [STARTUP_PROMPT.md](STARTUP_PROMPT.md)，状态与验收见 [PLAN.md](PLAN.md)。

独立前缀、模型、下载缓存、临时文件与新结果根为 `/mnt/d/humanoid-demo-r2`，源码仍在WSL Linux目录。C盘10GiB为系统运行余量，不是额外下载额度；100GiB为D上的项目容量规划。源视频完整保留，不自动截到60秒；当前先用原始上传即不超过60秒的视频，超限输入拒绝而不静默剪辑。

```bash
source scripts/activate-r2.sh
bash scripts/run-r2-demo.sh /absolute/input.mp4 my-run-id https://www.youtube.com/watch?v=VIDEO_ID
```

入口依次执行分阶段提取与缓存、官方SONIC坐标转换、复用R1的真实MuJoCo闭环，再生成完整时间轴的原片—2D/3D提取—实际状态三路MP4。结果在D根的 `runs/my-run-id/`；失败与所有中间结果保留，仿真停止后的画面明确标记，缓存复演不当作新的提取或物理验收。新run id用于新尝试，既有物理结果不会被自动覆盖。

环境配置见 `configs/environment-r2.yml`、`configs/constraints-r2.txt`，资源规则见 `configs/r2-resources.json`；固定GEM-X是Git子模块，独立环境不升级R1。当前已有的实际检查摘要见 [evidence/r2-setup-20261031.json](evidence/r2-setup-20261031.json)。

已安装版本导出为 [conda精确包清单](configs/conda-r2-linux-64.explicit.txt) 与 [pip锁定清单](configs/requirements-r2.lock.txt)。pip清单从仓库根目录使用，GEM-X取固定子模块；这些是本机版本快照，尚未进行新机器重装验收。

外部中断后可用下列入口恢复调试视频。它先核对原片、冻结源码/配置和已完成缓存；拒绝重复进程或已有失败/未完成物理结果。执行时等待空闲显存至少6144MiB持续15秒，默认最多观察1小时，保留每次尝试，不停止其他应用。

```bash
python3 scripts/resume-r2-demo.py --run /mnt/d/humanoid-demo-r2/runs/my-run-id --check-only
python3 scripts/resume-r2-demo.py --run /mnt/d/humanoid-demo-r2/runs/my-run-id
```

首片预检遭遇Windows非正常重启，另提供调试用姿态检查点入口；它复用官方FP32、batch1和翻转增广，实际整段/分帧数值相同后才保存每32帧结果。现有已证实的块逐一核对哈希，只有全部原始归一化帧完成才生成主入口可读取的pose2d完成缓存；辅助生产器和原冻结源码分别留存身份。非正常关机损坏的元数据须先保留、隔离并重算相应块，不能当作成功数据。

```bash
source scripts/activate-r2.sh
python scripts/run-r2-checkpoint-recovery.py \
  --extraction /mnt/d/humanoid-demo-r2/runs/my-run-id/extraction
```

该恢复入口默认每次最多新增3个32帧块，开算前等待温度低于60°C，并对元数据执行fsync/rename。可加 `--cycles 4` 连续执行最多4组：组间释放模型显存、至少休息30秒且等温度低于55°C，超过120秒未满足就退出等待。仅完成部分或等待资源时返回3，完整姿态完成才返回0。它不改变模型、视频内容或控制频率，也不能保证解决尚未查明的主机重启原因。当前全链路状态以PLAN为准。

身体/时序评估使用记录的实际qpos进行离线FK，并核对原生控制器录下的SMPL逐帧身份与时钟；不使用协议中全零的joint_pos占位字段作为机器人目标。输出各肢体角度误差、完整覆盖率和关键事件时间差，不拟合平移来美化对照。关键事件JSON需按原片预先标注并在保留测试前冻结；未提供时状态保持awaiting_verification。当前仅工具检查通过，R2实际结果待验证。

```bash
source scripts/activate-r1.sh
python scripts/evaluate-r2-body.py \
  --extraction /mnt/d/humanoid-demo-r2/runs/my-run-id/extraction \
  --physical /mnt/d/humanoid-demo-r2/runs/my-run-id/physical \
  --events /absolute/source-events.json \
  --output /mnt/d/humanoid-demo-r2/runs/my-run-id/body-audit-01
```

普通视频来源先用 `inspect-r2-sources.py` 做CPU全帧解码、来源哈希和等比例时间轴预览，再人工筛选单人/固定相机/全身脚部条件；全局画面变化与黑场仅作启发式提示，不自动宣称合格，不运行人体动作模型。已下载视频的标题/尾屏和不合格来源仍保留。

```bash
source scripts/activate-r1.sh
python scripts/inspect-r2-sources.py /absolute/video.mp4 \
  --output /mnt/d/humanoid-demo-r2/runs/source-review-NEW --samples 20
```

## R2 首片结果与当前边界

2026-11-01已在本机4060完成第一条普通YouTube舞蹈完整链路：27.933秒/838帧、1397个50Hz源参考，真实物理无跌倒，6/6预标注事件方向和顺序通过。这是调试首片，5+5整批和R2尚未完成，保留测试推理未使用。

- [完整三路视频](runs/r2-preflight-youtube-QqvZAUEOrAQ-20261031-01/demo-native-aligned-02/comparison.mp4)、[首片报告](runs/r2-preflight-youtube-QqvZAUEOrAQ-20261031-01/REPORT.md)。本地大产物不会随Git克隆下载。
- [可随Git同步的首片摘要](evidence/r2-preflight-20261101.json)、[实测资源/预算](evidence/r2-resource-estimate-20261101.json)。
- 对照保留完整时间轴、2D覆盖及对应3D骨架、真实记录状态离线渲染；无拟合时间偏移。八项身体角度误差约0.163–0.391rad只作报告，不能称为人体真值误差或R1关节跟踪误差。

物理录像单独恢复使用R1环境中的 `python scripts/run-r2-physical.py --reference <已完成提取目录>/sonic-reference.npz --output <已有物理目录> --render-only`。此入口只对已停止运行的实际状态按原生消费时钟重评/渲染，不启动控制器；已有录像必须先带哈希归档，不会自动覆盖。首片原始失败、旧派生录像及源码版本分别保留。默认整批入口的冷却检查点集成正在继续，状态以PLAN为准。
