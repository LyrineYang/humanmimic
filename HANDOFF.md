# HumanMimic：Linux迁移与R4交接

交接日期：2026-11-01，Asia/Shanghai。面向接手项目的人或代理，覆盖聊天中的执行约定、已验收事实、迁移限制和R4工作顺序。

> 本次同步修订：R1/R2原机器工程验收已完成，下一步是核对服务器已有记录并处理迁移/R4；不从旧启动段落重做R2。规范仓库已更名为`LyrineYang/humanmimic`。该次交接发布时`main`与`codex/linux-handoff`指向相同提交；当前主线以最新`main`为准，按[REMOTE_WORK](REMOTE_WORK.md)核对。用户提供的服务器目录`/home/junqiy/projects/humanmimic`与源WSL目录分别处理，历史路径/冻结清单不全局替换。修订前交接原文及SHA见[历史索引](docs/archive/README.md)。

这是交接快照；当前状态仍以[PLAN.md](PLAN.md)为准，历史证据以[EXPERIMENTS.md](EXPERIMENTS.md)及原始`runs/`为准，规则见[AGENTS.md](AGENTS.md)。不要把旧实验段落中的“正在运行”当成当前任务。

## 0. 最新服务器接续（2026-11-02，优先于下方历史快照）

- **当前E3优先与额度：** 用户确认144卡时、连续墙钟36小时、最多4卡；前置8/E1 12/E2 18/E3 72/余量34。E3保留360核心+144机制消融，E1缩72、E2缩144；见[当前方案](docs/r4-multimodal.zh-CN.md#12-e3优先的144卡时执行方案2026-11-02)。训练栈未完成、本批训练额度0；独立R4环境已具备显式估计与仿真依赖。新增调度与统计代码，标准库契约passed，GPU验收awaiting_verification。初检四卡均忙，收尾0/2暂空、1/3仍忙；完整四卡窗口未启动。成功抓取初始化、完整手力界与LEAP不确定性校准仍缺，主矩阵被证据门槛拦截。
- **环境/可用性交付：** 五项修复的原提交299e12a、cc98a3b、70640ca已随e4c50ac整合发布到main；旧提交由已推送archive标签保留。干净克隆/空前缀57-wheel安装、无私人资产CUDA首跑、8项运行契约、6项安装器契约、定向15/P2 15及最终环境P1 6项回归passed；普通查看0、严格验收3。当前入口`humanmimic.py doctor/bootstrap/example/inspect`，profile明确路径和执行范围。见[交付证据](evidence/runtime-portability-20261102.json)及`runs/runtime-portability-20261102-01/REPORT.md`。R2新目标仅只读诊断，原WSL保护未解除；研究收益仍未验收，网站浏览器渲染/发布未做。
- **指定审查修复：** 4项发现已逐项处理，GL_VENDOR沿用已有修复；并集外表面采样、VB纯二值输入及选帧隔离、shape-only独立逐帧位姿已修复。V100新增15项定向、原P2十五项和记忆/控制十八项回归passed；shape-only位姿准备计入共同预算，缺失时拒绝更新。未新增物理试次或操作通过结论，置信度校准仍待验。见[修复报告与复跑命令](runs/r4-review-fixes-20261102-01/REPORT.md)及[摘要](evidence/r4-review-fixes-20261102.json)。
- **当前接续：** 用户要求深入解释主线并继续代码/环境。本轮补全[直观解释、VideoManip对比、E0–E5/M1实验](docs/r4-multimodal.zh-CN.md#0-先读这一节推进什么为什么以及交付什么)，实现显式持久记忆、CUDA FK/IK、几何×力反馈局部控制、任务代理探触、独立在线进程和E2/E3入口。既有V100核心环境足够，无新增依赖；使用`source scripts/activate-r4-research.sh`，运行前仍查GPU占用。
- **当前证据：** P1六项、P2十五项、记忆/控制十八项、统计五项CUDA检查passed；已执行完整LEAP在线负对照并保存物理录像。解析精度与数据隔离已验证，位姿区间偏窄、20种子覆盖率未做，成功抓放/几何操作收益尚未证明。P3是参考附近局部修正，P4未标定力界默认拒绝，WSM没有训练/权重接入。原失败与修复、最新回归位置见`runs/r4-memory-control-20261102-01/REPORT.md`；本轮没有CPU测试、保留/付费/真机使用。

以下P1/P2“未执行”和CPU原型条目是前两轮历史，不覆盖上面当前证据。

- 用户进一步要求推进P1/P2并明确不要CPU检查。四指LEAP触力桥、公开观测/私有评价分流、独立CUDA联合位姿/局部网格/有效顺应性估计、GPU校准/覆盖率/E1重放与评价源码已写入；本轮未执行CPU检查、源码解析或GPU任务，新增验收全部awaiting_verification。接续命令/局限见[多模态文档第9节](docs/r4-multimodal.zh-CN.md#9-p1p2实现与gpu运行准备2026-11-02)，原始准备记录`runs/r4-p1p2-implementation-20261102-01/`。不能继承此前原型passed，不能将E1感知精度当E2操作精度。

- 用户随后提出WM-CraftNet多模态状态/触力觉用于重建及操作的研究目标；[详细方案](docs/r4-multimodal.zh-CN.md)已完成源码对照、库选型、实施步骤、E0–E5试验与CPU原型。30项测试和原生触力探针通过；没有新GPU/训练/操作成功结论，MANO将直接由用户发送。最新接续以PLAN为准。

- 仓库 `/home/junqiy/projects/humanmimic`、origin `https://github.com/LyrineYang/humanmimic.git`，基于a8a58e6、分支codex/server-research；用户仍核查原机遗漏。后续最新状态见PLAN。
- 用户进一步授权R4方案、独立环境与运行准备；已完成[第一阶段方案](docs/r4-stage1.zh-CN.md)、V100核心栈/LEAP资产、12开发对象观测、导入/碰撞/物理评价实现。17项测试、CUDA和NVIDIA EGL运行passed；物理负对照抓取failed符合预期，不是R4操作能力通过。
- 安装网络已经通过用户7893代理解决；原27891域名拒绝是历史。独立数据根humanmimic-data/r4约8.9GiB，启动source scripts/activate-r4.sh；下方旧WSL环境不可直接复制。源文件和现有人工改动保留，未提交/推送本轮改动。
- MANO用户拥有授权、路径稍后提供；完整视频前端子环境/权重、DexYCB序列/CAD、规划器与六种几何方法的操作闭环尚未完成。P2局部网格联合优化已有源码，待GPU验收。当前不从零训练、调用付费API、执行正式保留集或连接真机。
- R1/R2原机验收/已用测试不变，R3跳过。源码、环境和准备物理/录像分项通过不转移为新机R1/R2或R4整体验收；原始报告runs/r4-stage1-preparation-20261101-01/REPORT.md。

## 1. 接手先做什么

1. 读本文件、PLAN当前状态/验收和AGENTS；需要具体证据再读EXPERIMENTS及各片报告。沿用既定路线。
2. 核对Git提交、已有修改、目标机器、任务PID/启动时间/boot与日志；观察超时不等于失败，勿重复提交。
3. 旧交接编写时尚未连接服务器；当前已进入上述服务器并完成R4核心运行准备。准备任务已结束；其他GPU负载会变，按PLAN与第0节核对当前进程再运行。
4. 首次交接快照中的源WSL boot是`da152f79-87d4-4995-876b-7bb6b59456c8`，已不同于R2验收时的`fa0233fb-701c-42d8-81da-0d007d2efe7d`。这说明WSL启动身份变化，不能据此断定Windows关机原因。按用户“再次关机则转服务器”的约定，不恢复本机GPU重试，也不改旧boot保护绕过它。
5. 服务器R4独立核心环境与准备试次已建立；完整视频前端仍待接通。源机器的passed标签不自动转移到服务器。

历史源快照（首次交接编写时）：`9808b0393a778eae4b7308abd11224359acf8abc`，原分支`codex/project-homepage`；本交接在`codex/linux-handoff`分支整理。R2完成提交`59c6ded`，R2运行冻结提交`42463b0`，英文主页内容提交`ff1c621`。接手时再核对实际HEAD，不强制退回这些历史提交。

服务器获取本交接分支的示例（只拉代码，先确认目录/权限和私有仓库认证；本轮未执行）：

```bash
export SERVER_PROJECT="$HOME/projects/humanmimic"
GIT_LFS_SKIP_SMUDGE=1 git clone --branch codex/linux-handoff --recurse-submodules \
  https://github.com/LyrineYang/humanmimic.git "$SERVER_PROJECT"
```

跳过LFS不等于资产已准备；后面列出的模型、真实LFS实体、环境和结果需另行私有迁移。若分支之后已合并，使用用户确认过的最新版本。


## 2. 用户已确定的偏好与授权

- 用户偏好conda。R1和R2隔离，不用升级已验证的R1来解决R2依赖问题。
- 代理负责部署、实现、验证和修复；额度内常规工作持续推进，不每个检查点都重新要确认。先把方案做成可审阅结果，再提出真正需要用户决定的问题。
- 只做仿真。未授权真机连接、从零训练、付费云资源、系统驱动/风扇/功耗修改或重装系统。Modal的30美元是历史报告额度，余额未验证，计费执行仍未授权；以[budget.json](configs/budget.json)为准，新增云支出为0。
- 当前已实测服务器为4×V100-SXM2-32GB，驱动530.30.02，内存约251.6GiB；硬件观察完成，软件栈和控制验收尚未完成。详见本机盘点，不再重复等待服务器连接。
- 优先吞吐，不人为低温等待、不逐帧休息、不强制组间冷却；保留真实温度记录和32帧持久化检查点。硬件温控保持原状；再次本机关机后转已有服务器，不反复本机试错。见[执行策略](configs/r2-execution-policy.json)。
- 大环境、权重、缓存、临时文件和结果集中规划到数据盘。原100GiB是D盘容量规划，非独占配额，不创建占位大文件；源代码、Git和原R1环境仍在WSL/C。服务器需重新指定实际数据卷。
- Demo要完整展示“原视频—2D覆盖—估计3D人体/骨架—实际仿真”。保留原片、所有数值中间结果、失败、时间映射和各路视频；不剪去失败段，不拟合时间偏移美化结果。原视频音频仍在原片，现有comparison为静音。
- 网站展示名HumanMimic，仓库`LyrineYang/humanmimic`仍private。英文主页已发布到既有仓库默认分支；不新建仓库、公开模型/受限资产或擅自部署网站。

## 3. 已完成与未完成：不要从头再做

| 阶段 | 已有证据 | 状态边界 |
| --- | --- | --- |
| R1 | 固定5动作各2次，10/10通过，5/5动作双次通过；6300控制样本，无跌倒，29关节RMSE约0.10875–0.17517rad | 4060/WSL上的`passed`；目标Linux服务器尚未验收 |
| R2 | 固定5调试全部报告：3passed/2failed；5保留全部报告：4passed/1failed，达到原≥4/5门槛 | R2工程验收`passed`，不是任意视频泛化/人体3D真值/实时验收 |
| R3 | 用户明确本阶段跳过现场相机 | 历史未验收；不标passed，不阻塞R4 |
| R4 | LEAP桥、联合估计、显式记忆和局部控制/探触已实现；GPU分项与在线负对照有证据 | 整体`awaiting_verification`；成功抓放、置信度校准、方法收益和正式保留未完成 |
| 项目展示 | 英文README、研究/insights/架构/结果文档、原创SVG、静态网页原型与小型demo帧 | 私有GitHub主页发布已核验；独立网站未部署 |

当前R2的10个试次均物理稳定，12095个源参考完整消费，其中保留5784；50个MP4全解码、实际状态/视频SHA和视觉审计通过。物理稳定不等于动作事件通过。

### 权威结果与完整演示

以下 `runs/` 链接是原机证据位置，本次 Git 克隆没有对应原始结果/录像；当前可直接读取的是 Git 内的 evidence 摘要。保留原链接便于原机追溯，不将本地缺文件解释为原验收未发生，也不宣称已完成证据迁移。

- R1原始验收：[runs/r1-suite-acceptance-20261029-03](runs/r1-suite-acceptance-20261029-03/)，主要看`REPORT.md`、`suite-audit.json`和全部十次记录。
- R2原始验收：[完整报告](runs/r2-suite-acceptance-20261101-01/REPORT.md)、[suite-summary.json](runs/r2-suite-acceptance-20261101-01/suite-summary.json)、[artifact-review.json](runs/r2-suite-acceptance-20261101-01/artifact-review.json)、[逐片CSV](runs/r2-suite-acceptance-20261101-01/source-results.csv)。
- Git可携带摘要：[R2验收JSON](evidence/r2-acceptance-20261101.json)、[结果说明](docs/results.md)。小型预览在`evidence/`和`docs/assets/`，大视频不随Git克隆下载。
- 保留队列原始日志与收尾：[r2-heldout-orchestration-20261101-01](runs/r2-heldout-orchestration-20261101-01/)，包含`frozen-identity-review.json`、`storage-cost-review.json`及`progress.json`。调度器因存在失败源而退出failed；最终冻结汇总按≥4/5规则passed，两者口径不同，勿改写原日志。

| 分组 | 视频ID | 事件 | 整片 |
| --- | --- | --- | --- |
| debug | QqvZAUEOrAQ | 6/6 | passed |
| debug | 0EpP3pYUYTk | 7/7 | passed |
| debug | vTx_ldn6MCA | 3/4 | failed |
| debug | 6uqztDO_7kQ | 0/6 | failed |
| debug | 2e_7XBmpw14 | 5/5 | passed |
| heldout | ROZy7jawHf4 | 8/8 | passed |
| heldout | U7Nrwyu6Uqo | 6/6 | passed |
| heldout | gRexOgq8h-8 | 6/6 | passed |
| heldout | dIfUVvoVXRM | 5/5 | passed |
| heldout | GP4YqDYMmcI | 5/6 | failed |

**需要记住的失败：** 臂环绕末尾右腕外展未达原≤0.2要求；踏步原试次22/574源参考后真实跌倒，统一初始化后574/574稳定但原侧别/事件仍0/6。最后保留GP4YqDYMmcI在22.4–23.5秒的`left_knee_flexion_rad`原阈值0.7，提取max0.481388、机器人0.414427，整片failed。单目侧别/深度/标注根因未独立确认，不将数值当3D真值，也不按结果改标签。

GP4YqDYMmcI的canonical `run-audit.json`保留失败初审、visual待验字段；最终`run-audit-visual-20261101.json`补充了passed媒体/视觉，整片仍failed。其682帧完整对照、`failure-event-review.json`和失败时点图都要带走；仅看初审的visual字段会误认为证据缺失。

**所有5条R2保留均已使用。** [冻结清单](configs/r2-suite-frozen-20261101.json)SHA256是`c3403dc4581ed61880e66f3c4cbbaa84961c1455621c0e5f170c10c0006378d1`；其中false表示“冻结时未使用”，当前使用看D盘`runs/heldout-use-ledger.jsonl`。迁移回归不能重置台账或再称这些视频为未见测试。三条保留舞蹈同创作者/相关场景，工程结论有该限制。

## 4. 现有实现中不能丢失的细节

- 预训练策略、增益和主要控制器保留；修复的是仿真绝对deadline，避免相对sleep累计漂移。50Hz控制、200Hz仿真，实际原生CSV与同一tick参考对齐，无拟合平移。
- 默认G1有自由根部，重力/接触/扭矩控制启用；播放期间弹力带关闭，无逐帧实际qpos/qvel覆写或自动复位。参考姿态动画不是实际控制证据。
- R2串行八阶段：prepare、detect、features、pose2d、camera、motion、postprocess、convert。完整源≤60秒，超限拒绝而非静默剪辑；批1、原生FP32和flip设置固定。
- `r2_initialization.py`：50帧中立静置+100帧/2秒固定参考过渡，然后全部原源样本；future context为51。源字段原值不变，视频0对应150帧前缀之后，评估器同步这一明确时钟。
- `r2_detection.py`固定CPU ORT 8/1线程；已在调试完整344帧证明输出等价。顺序读帧避免重复GOP seek；离线实际渲染仅关闭阴影/反射，物理及相机/时间映射不改。不要把局部23倍解码提速当整链路提速。
- R2只读缓存验证包括原片SHA、源码快照、八阶段marker与全部产物SHA，见`r2_cache.py`。新调试控制回归复用原提取缓存，实际控制/事件/demo重跑；不能把缓存回放声称为新动作提取。
- DDS只走`lo`，ZMQ只走localhost；Unitree DDS配置1200字节消息/1024字节分片。Python CycloneDDS 0.10.2与SDK配套C/C++ 0.10.2匹配；旧预编译Python wheel曾携带C 0.11导致问题，勿任意替换。
- C++链接使用RUNPATH处理本地SDK依赖，旧式RPATH曾覆盖预期库选择。复制库和二进制后仍要查动态链接，不靠“能import”判定控制器可用。
- 当前子模块`vendor/GR00T-WholeBodyControl`有已知DDS本地补丁；必须保留[补丁](patches/sonic-loopback-dds.patch)，不要reset或强制更新清掉它。
- 当前EGL画面是Mesa llvmpipe CPU软件渲染，GPU计算成功不代表GPU图形窗口通过。源码/环境、动画/回放、无界面控制、现场相机必须分项报告。

主要入口及用途见[架构](docs/architecture.md)、[准备指南](docs/getting-started.md)。先用现有接口，不假设已有R4 runner或一键Linux迁移脚本。

## 5. 原机环境与资产参考清单

### 5.1 锁定源版本

- SONIC：`45c03facbf848e0c743091b7d9c17952096ff908`，含上述DDS补丁。
- GEM-X：`20555befe2fbbe5b2015e1fff7ff214dc18ea9d6`。
- Git仓库：`https://github.com/LyrineYang/humanmimic`，需要既有私有仓库权限；不要把Git/HF token写进命令、文档或Git。

| 组件 | R1 | R2 |
| --- | --- | --- |
| conda prefix | `.local/miniforge3/envs/humanoid-r1` | `/mnt/d/humanoid-demo-r2/envs/humanoid-r2` |
| Python | 3.10.22 | 3.12.16 |
| PyTorch | 2.7.1+cu128 | 2.10.0+cu128 / torchvision0.25.0+cu128 |
| 数值依赖 | numpy1.26.4、scipy1.15.3 | numpy2.2.6、scipy1.15.3 |
| 执行/感知 | MuJoCo3.3.7、CycloneDDS0.10.2、官方SONIC/Unitree SDK | transformers5.3.0、py-soma-x0.3.3、warp1.18.0、ORT CPU1.31.1、OpenCV-headless4.14 |
| 原生依赖 | TensorRT10.13.3.9、CUDA开发工具12.8.93、ONNX Runtime **C++**1.22.0、Eigen3.4 | 控制阶段仍调用R1环境，不使用R2 ORT替代SONIC TensorRT |

环境定义、constraints、pip与linux-64显式conda快照在`configs/`。pip快照含本地editable源码；`pip install -r`不是完整原生SDK安装器。保留两套Python/NumPy，不合并环境。

### 5.2 Git克隆不会带来的内容

| 源位置 | 内容与迁移要求 |
| --- | --- |
| 项目`models/sonic-default/` | 原SONIC encoder/decoder ONNX、observation配置、规划器等；先核对[r1-suite.json](configs/r1-suite.json)中的SHA，勿只迁移TensorRT缓存 |
| 项目`vendor/GR00T-WholeBodyControl/gear_sonic/data/robot_model/model_data/g1/` | G1真实XML/URDF/mesh等LFS实体；clone跳过smudge后可能只有指针 |
| 同子模块`gear_sonic_deploy/reference/example/` | 固定五动作及Macarena初始化样例的真实CSV/metadata；不能缺失或偷偷换动作 |
| `/mnt/d/humanoid-demo-r2/models/` | GEM-X/SOMA/SMPL授权资产、映射及SONIC D盘副本；按冻结15资产SHA核对，受限资产仅通过获授权私有通道迁移 |
| `/mnt/d/humanoid-demo-r2/sources/` | 完整源视频、来源资料；保留原片与镜像/时间约定 |
| `/mnt/d/humanoid-demo-r2/runs/` | 全部R2原始结果、检测/2D/3D/转换缓存、参考/实际状态、失败、录像、台账、源码快照、profiles及最终报告 |
| WSL项目`runs/` | R1完整验收/此前失败、环境/构建证据、展示检查；大量R2条目是指向D盘的**绝对symlink**，仅复制这些链接不等于复制结果 |
| 项目`.local/` | 现有Miniforge/R1环境、TensorRT、ORT C++、DDS库/链接、构建源与缓存；优先按下面兼容性结论重建运行环境，必要时仅私有归档所需目录 |
| `docs/`、`website/`、`evidence/` | 在Git内；英文主页和本地静态原型要一并带走，小型预览不等于完整demo |

R2收尾D根实占19.884GiB；本轮只读测得WSL `.local/`额外约15.56GiB、根`models/`约0.89GiB，另外还有WSL `runs/`和vendor本地资产。**19.9GiB不是整个项目备份体积**，这些占用也不等于必须传输的数据量；conda包缓存/编译缓存可重建。迁移前按白名单统计，别整包复制用户HOME、Git/SSH配置或HF认证目录。模型文件可迁移，凭据在服务器独立配置。

## 6. Linux迁移：先兼容性，再安装

### 6.1 V100分支是实质兼容风险

目标现已确认为V100（Volta/SM7.0），不能原封不动复用原4060环境：

- 官方明确TensorRT10.4是最后支持Volta的版本，10.5起移除，因此现用10.13.3不支持V100。候选是独立的Volta兼容TensorRT10.4用户态栈，并检查SONIC C++ API/插件和ONNX支持，再重编译控制器；**这是待验证方案，不是已经完成的迁移**。[NVIDIA架构说明](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/architecture/architecture-overview.html)、[10.4发布说明](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/release-notes-10/10.4.0.html)。
- 原机交接阶段只读取了已安装库的编译元数据，没有启动CUDA内核；这些库尚未在本机安装：R1 `2.7.1+cu128`编译列表**不含sm_70**；R2 `2.10.0+cu128`列表**包含sm_70**。R1需另选兼容轮子/构建；R2仍须验证驱动、SOMA/Warp及完整模型阶段，不能由一个架构标志判整链路通过。原始列表见`runs/linux-handoff-20261101-01/inventory.json`。
- 不执行无约束的`pip install -U torch`。后续PyTorch CUDA12.8构建对Volta支持也有版本边界，按服务器选定版本及实际`torch.cuda.get_arch_list()`核实，保留单独server锁文件。[PyTorch官方发布工程说明](https://dev-discuss.pytorch.org/t/dropping-volta-support-from-cuda-12-8-binaries-for-release-2-11/3290)。
- 迁移ONNX和原始权重，在目标GPU重建engine/plan/时序缓存。没有显式验证的硬件兼容模式时，TensorRT engine不能假定跨GPU复用；旧缓存只保留作历史。[TensorRT支持矩阵](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/support-matrix.html)。
- 四卡不自动成为单卡128GB，也不自动加速现有串行runner。先单卡建立稳定基线；并行候选另做进程、DDS域/端口、日志和随机种子隔离。

上述支持关系于2026-11-01核查；本机只读盘点已确认V100，另有glibc2.27、Docker socket权限和FFmpeg缺库问题。仍不更改服务器系统驱动，也不安装笔记本驱动号617.42；独立用户态方案及目标机运行均待后续验证。

### 6.2 推荐布局与需要适配的实际代码

布局是建议，先核对用户可写的数据盘再确定，不要求固定账户或`/srv`权限：

```text
SERVER_PROJECT/                 Git源码（例如 ~/projects/humanmimic）
  .local/                       新建的R1 conda/原生SDK入口
  models/sonic-default/          原始ONNX/配置，来源SHA不变
SERVER_DATA/                    真实数据盘，路径由服务器确认
  envs/humanoid-r2/             独立R2环境
  models/ sources/ cache/ tmp/  新服务器自己的模型与缓存布局
  archive/wsl-project-runs/     保留原WSL证据，不批量改写JSON
  archive/wsl-r2/               原D盘资产/结果的私有归档
  runs/server-<run_id>/         新服务器的独立试次
```

| 代码/文件 | 现有限制 | 待实现的迁移动作 |
| --- | --- | --- |
| `scripts/activate-r1.sh` | 项目内Miniforge及10.13.3/ORT/DDS固定入口 | 重建或显式配置server conda/SDK路径，检查库与RUNPATH |
| `scripts/activate-r2.sh` | 支持`R2_STORAGE_ROOT`，但含WSL库路径 | 设置真实server数据盘；检查native Linux动态库路径，保留全部cache/TMP到数据盘 |
| `scripts/r2_common.py::storage_check` | 强制检查`/mnt/c`、`/mnt/d`和owner marker | 新增明确server卷配置及目录归属检查，**不能只设置环境变量就宣称可迁移**，也不伪造盘符绕过检查 |
| `configs/r2-execution-policy.json`、`run-r2-suite.py` | 旧机器boot保护、冻结GPU/驱动/二进制/源码校验 | 保留原文件/冻结证据；建立独立server运行策略和可追溯运行身份，不编辑旧boot/旧冻结来冒充同机续跑 |
| 原`runs/`与快照JSON | 绝对symlink、绝对路径和旧PID/boot | 私有归档保留原字节/SHA；新建路径映射/结果索引，重建工作目录symlink；旧PID不能作为服务器任务句柄 |
| R1 suite与R2 frozen manifest | 含原二进制SHA、代码/资产/硬件身份和已使用数据 | 新运行身份单独记录，源动作/策略权重/评价规则保持；迁移复验明确标记regression，不篡改历史passed |
| `r2_cache.py`及缓存复用入口 | 来源指纹、debug/heldout及目录归属有约束 | 复用前核对完整八阶段及原快照；按显式迁移记录接入旧参考，不重标heldout为未见debug绕过保护 |

原R2冻结清单不要改。适配后的源码/配置形成**新的server版本与试次身份**，归档原冻结清单及其SHA。现有`freeze-r2-suite.py`会拒绝已使用的保留视频，不能删台账、清used标志或改角色来过检查；若需要全套R2迁移复验，应实现明确的“已使用数据迁移回归”配置/入口，而非伪装新的heldout验收。

### 6.3 未来获准安装/运行后的迁移次序和放行证据

1. **只读硬件预检已完成；运行就绪仍awaiting_verification。** 记录目标OS/CPU架构、GPU型号/UUID/驱动、可见卡数、RAM、数据卷空闲、现有conda和权限。目标架构不是linux-x86_64时，原linux-64显式包单不能直接套用。

   ```bash
   uname -a
   uname -m
   cat /etc/os-release
   nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total --format=csv
   free -h
   df -h
   command -v conda
   ```

2. **源码对账与独立资产准备。** 用户核查未上传源码后按Git差异合并；本机环境/模型按获准来源和SHA独立配置。若以后确需私有归档旧结果，先dry-run与白名单，再通过用户既有通道传实际文件，保留所有失败和中间结果，不使用`--delete`清旧文件。`rsync -a`会保留symlink，指向`/mnt/d`的绝对链接必须另作新工作映射；不盲目解引用整棵目录。先核对目标接收到的文件SHA，再宣称迁移完成。现有源资产仍在原机，不先删除。
3. **独立conda/原生SDK。** 以已记录版本为起点，按实际GPU兼容性选择server构建，保留两环境和新的server锁文件。Conda显式文件用于同平台复现，不证明GPU/驱动/原生SDK可用；原目录`cp`过去不等于prefix已重定位、editable安装和动态链接已恢复。[Conda环境文档](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)。
4. **代码适配与编译。** 只在新server版本完成上表适配；按授权来源准备DDS/TensorRT/ORT C++和真实LFS资产，应用已有DDS补丁一次、重编译`g1_deploy_onnx_ref`，在目标卡重建引擎。检查匹配SDK C/Python DDS及实际链接，不能把ORT CPU依赖悄悄当TensorRT替代执行器。
5. **环境与基础运行。** 完成CUDA数值、模型导入/前向、DDS loopback收发、G1加载/步进、真实单动作闭环和实际状态录像检查。`scripts/check-r1-environment.py`是已有环境检查入口，但其中包含CUDA计算和基础物理，**不是纯只读命令**；仅在上述准备后运行。环境import通过不代表控制passed。
6. **R1目标硬件复验。** 环境/二进制变化后，以原5动作各2次、原RMSE≤0.35/无跌倒/完整消费规则建立新server结果；新manifest记录新二进制/GPU，保留原动作/策略/评价SHA。原4060十试次不覆盖。先检查`prepare-r1-suite.py`、`audit-r1-suite.py`实际参数，不假设旧二进制SHA会自动适应。
7. **按R4依赖做最小R2迁移回归。** 若使用已保存的SMPL参考，先用已有debug参考验证完整流式控制、150帧初始化、原生时钟、身体评估和真实录像；无需为了R4先重做所有视频的重型提取。若要宣称服务器上的R2完整链路通过，再验证所有模型阶段和对应整批迁移回归，并标记已用数据；后续调参需要新预划分测试。
8. **按实际依赖进入新R4。** 独立灵巧手分支可先建立自己的物理/重建基线，无需等待所有R1/R2重跑；若采用SONIC/G1则先完成对应复验。固定硬件、输入、控制权重和评价规则，按新研究报告做对照。分项记录环境、代码、回放、物理验收；R3本阶段跳过，不凭旧机结果提前通过。

暂未实现的server路径适配、V100构建和迁移回归都没有现成一键命令。本文件不假造`setup-server.sh`或R4 runner。

## 7. 原R4已知几何基线（历史方案）

原方案如下，保留其[原始门槛](PLAN.md#r4-场景约束动作修正)以便回归：**冻结SONIC，只修改参考动作；主要固定双脚、单臂伸手、一个静态箱体、已知仿真几何；先离线搜索。** 用户现已扩大R4范围，此方案不再限制场景重建或接触丰富研究，也不代表新R4完整验收。当前路线见[研究报告](docs/research-video-interaction.zh-CN.md)；训练和运行仍需遵守当前授权。

### A. 场景、参考与评价接口

- 从已通过参考中选择/构造一段完整单臂伸手，在无障碍时先证明原SONIC能稳定达到目标；保存原始来源及派生规则，不改写R1/R2历史输入。
- 在MuJoCo实际物理场景加入箱体碰撞geom；纯画面画一个盒子不够。记录世界/机器人/人体参考坐标、尺度、初始位姿、脚部支持和同一个伸手目标。
- 先确认控制器实际读取的参考表示。R1 CSV和R2 SMPL流不是同一种输入；IK产生的机器人关节角不能未经转换当成SMPL字段。修改参考后更新/校验相关FK、旋转、速度和时间戳，不能只改腕点或joint_pos而留下矛盾字段。
- 只修改参考，不修改实际状态来替代控制执行。实际状态始终由扭矩控制和仿真产生；可离线用模型求FK/IK，但执行时不逐帧写实际qpos来“保证”无碰撞。

### B. 两个小规模决定性实验

1. **修正可用性：** 一条改过的参考在真实SONIC闭环中能到达原目标、避开箱体并保持稳定。
2. **几何与执行的差距：** 找到/检验运动学与距离筛选通过、真实控制仍失败的情形，判断闭环筛选的价值。若没有这类证据，不宣称已证明“执行风险预测”的必要性；不把这两个例子当完整R4验收。

这一阶段失败就修复输入表示、尺度、IK或场景接口，别先扩成大量布局/训练任务。

### C. 参考修正与有界搜索

- 少量腕部路径控制点，围绕原动作生成确定性、带seed的有限候选；保持原目标/终点、动作时长和特征，限制关节/速度/加速度与根部、脚部偏移。
- IK、关节限制、自碰撞及机器人各相关部位到箱体的距离先筛选；只看腕部无碰撞不代表肘/前臂/躯干无碰撞。
- 给幸存者分配固定上限K次真实闭环回放，记录全部候选、失败、筛除原因与开销；K及偏移边界在开发集确定后冻结。
- 先满足真实到达、碰撞和稳定性，再在有效候选中比较动作偏差/开销；无解就报告失败或拒绝。不能用不动、不到目标或把目标移到箱体前来骗过碰撞指标。
- 首版用固定预算确定性搜索。研究文档中的自适应分配/风险预测属于后续条件性方向，不是本轮已实现功能或强制训练前提。

### D. 四个对照与开发集

同一场景、源动作、目标、GPU、策略权重、初始化和评价：

| 方法 | 用途 |
| --- | --- |
| 原动作 | 确认障碍造成的真实碰撞/任务失败 |
| 仅缩小幅度 | 简单基线；仍必须达到同一目标 |
| 几何修正、无闭环筛选 | 消融，分离几何编辑与执行验证的贡献 |
| 完整修正+有界闭环筛选 | R4完整方法 |

只在10个开发布局调参数。每种方法报告实际物理调用数和时间，包含失败候选；若后续比较“相同预算更优”，须另外控制等预算，不能忽略完整方法多用的回放。

### E. 冻结与完整验收

- 另冻结至少20个未调试布局、seed、几何/目标、稳定/碰撞/到达判据和动作偏差算法；距离裕量、容差、脚漂移/关节速度等具体数值尚未定，须在开发集确定，不能看测试结果再调。
- 对20个及以上保留布局跑全部四种方法，保留全部成败；使用过就标记，不再称未见。
- **至少3个保留布局**满足：原动作真实碰撞；完整方法实际无碰撞、稳定、达到**同一个**伸手目标。
- 全体布局报告成功率、碰撞率、稳定性、动作偏差、计算时间及回放次数；至少交付3组完整对照录像，包含失败/中间结果和最终实际状态。
- 实现代码、一个漂亮例子、三个挑选的成功例子或预算用完都不能代替完整验收；没有改进就如实记录否定结果。工程改进不自动等于论文级首创。

### F. 拟新增产物（当前不存在，名称可按现有风格调整）

`configs/r4-development-layouts.json`、`configs/r4-evaluation.json`、独立的冻结保留布局清单；参考候选生成/IK筛选器、场景闭环runner、批次汇总与完整对照渲染入口。它们应复用现有绝对节拍、实际状态记录、版本/哈希、失败与恢复机制，输出`runs/r4-<run_id>/`。

每个结果包至少包括：输入/场景/策略/代码身份、候选参考与FK/距离记录、筛选原因、实际rollout/接触/腕部到达/稳定数据、候选与总开销、四方法汇总、完整录像和REPORT。先实现这些可审计接口，再考虑多卡提速；DDS同域进程可能互扰，现有端口随机化不等于已支持多实例隔离。

## 8. 仓库展示工作也要交接

英文README、[architecture](docs/architecture.md)、[results](docs/results.md)、[insights](docs/insights.md)、[research](docs/research.md)、[getting-started](docs/getting-started.md)已交付，旧中文README保留在[operations.zh-CN.md](docs/operations.zh-CN.md)，后者是历史归档。

静态`website/`无构建、后台、外部字体或分析服务；1440/768/390/320宽度、筛选和无JS退化已测。它只含小型静态预览，不假装有完整视频播放器。结果表是静态验收快照，改变正式结果时同步页面、README、日期与docs，不改历史JSON来迎合展示。

[网站交接](docs/website.md)包含布局和后续托管说明。独立网站尚未部署；远程本地预览需要SSH转发。生产发布只打包`website/`和其引用的`docs/assets/`等必要内容，不能把包含内部计划、`.local/`和`runs/`的整个仓库根作为公开document root。对外公开受众、素材许可及托管目的地仍需另定。

## 9. 可交给下一位代理的接续文本

以下为当前服务器的接续范围，覆盖旧“静态箱体优先”提示：

```text
先读AGENTS与PLAN当前状态/验收，再读本机盘点、R4研究报告和HANDOFF。origin已改为humanmimic并同步a8a58e6，文档分支codex/server-research。用户核查原机未上传代码；环境与资产本机独立配置。
本轮只更新远端/链接、只读盘点和深入研究，暂不安装依赖或启动实验。R3本阶段跳过，R4主线为视频手物/交互对象细粒度重建与灵巧操作。静态箱体方案仅保留基线，不是研究上限。
4×V100已确认，但Volta/TRT、旧glibc、Docker权限和FFmpeg等尚未解决。现有GPU0负载不干扰，不改驱动或系统。R1/R2原机passed不转移；旧冻结清单、失败、已使用保留集全部保留，新机以后建立独立身份。
未来运行获准后，优先手型物理基线和本地视频重建基线，固定控制器评价几何误差与操作精度的关系，再冻结新保留集与完整对照。付费API、训练和真机未授权。按PLAN更新状态、EXPERIMENTS追加证据，不把准备材料当成能力验证。
```
