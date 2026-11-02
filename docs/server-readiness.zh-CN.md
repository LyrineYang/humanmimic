# HumanMimic 本机迁移盘点

检查日期：2026-11-01。范围是只读环境观察、兼容性分析和待办整理；未安装依赖、下载模型、启动容器、执行 CUDA 运算或仿真实验。原始输出位于 `runs/migration-research-20261101-01/`，可同步摘要见 [evidence](../evidence/server-research-20261101.json)。

> 后续状态：用户随后授权并完成R4独立核心环境和小规模准备验证。7893代理下载、V100数值计算与EGL物理录像已经通过；完整视频前端仍待接通。见[第一阶段方案与实测结果](r4-stage1.zh-CN.md)。本文下方保留安装前快照，不代表当前全部缺口。

> 2026-11-02新增：显式多模态记忆、局部几何/力控制与探触代码复用同一r4-core，不需要新增依赖。`activate-r4-research.sh`设置SM70/确定性与独立缓存；P1/P2和控制模块已在V100执行CUDA检查，在线仿真链已接通。MuJoCo动力学为CPU，GPU承担估计、规划数值与EGL；未运行CPU测试，不宣称实时控制。WSM原生环境/权重、完整视频前端、MANO路径与真实数据仍未准备齐全，见[最新实现与证据](r4-multimodal.zh-CN.md#10-当前实现环境与运行入口)。

## 1. 仓库与源代码

- 项目根目录为 `/home/junqiy/projects/humanmimic`，没有外层同名仓库嵌套。
- `origin` 已改为 `https://github.com/LyrineYang/humanmimic.git`；fetch 后从 `9808b03` 快进到 `a8a58e6c6b7aaac36ad530a2b6682ef778e936fe`，纳入迁移 handoff 和主页可用性更新三个提交。本次整理使用 `codex/server-research` 分支，尚未提交或推送。
- 更新当前文档与网站中的仓库链接；原机绝对路径、历史实验记录、冻结清单保留原样，不能用字符串替换破坏溯源。
- SONIC、GEM-X 子模块尚未初始化，项目自己的运行环境和模型资产不存在。记录了固定提交，并不等于依赖源码及 LFS 实体已经齐全。
- 用户正在核查原项目未上传代码。后续按 Git diff、未跟踪文件、子模块改动与已有 DDS patch 对账；本轮不能断言原机所有工作均已同步。

## 2. 实测硬件与系统

以下是 10:29 UTC 的宿主机快照，可用量会变化。普通沙箱看不到完整驱动设备，因此采用获准的宿主只读查询，不能把沙箱访问失败解释为驱动故障。

| 项目 | 实测 | 对迁移的影响 |
| --- | --- | --- |
| GPU | 4 × Tesla V100-SXM2-32GB，单卡 32768 MiB，SM 7.0 | 四张卡有独立显存；不是可任意使用的单卡 128GB |
| 当前占用 | GPU 0 有现存 Python 计算进程，观察时约 535 MiB、利用率 100%；GPU 1–3 未见已分配显存 | 不干扰既有进程；后续开工重新核对空闲和授权，不能把观察时空闲当独占 |
| 驱动 | 530.30.02；`nvidia-smi` 显示 CUDA 12.1 | 该标签不是已安装 toolkit 版本，也不是所有 CUDA 12.x 软件的绝对上限 |
| CUDA toolkit | 11.8.89 和 12.1.66；`/usr/local/cuda` 指向 12.1；当前 PATH 无 `nvcc` | 后续每个环境显式选择工具链，避免混用编译器和运行库 |
| CPU | 2 × Xeon Gold 5117，28 物理核 / 56 线程，2 NUMA | 可承担解码/几何处理；并行调度仍需按实际负载分配 |
| 内存 | 总约 251.6 GiB，可用约 244.0 GiB；Swap 8 GiB | 容量充足不证明具体模型或并行仿真可运行 |
| `/home` 数据卷 | 总约 7.22 TiB，余约 680.3 GiB，使用率 91% | 当前项目位于此卷；应规划环境、模型、缓存与结果的共同上限 |
| `/` 系统卷 | 余约 57.2 GiB，使用率 97%；`/tmp` 在此卷 | 大型下载、解压、编译及临时缓存应迁到数据卷 |
| OS / ABI | Ubuntu 18.04.6、内核 4.15.0-213、glibc 2.27、x86_64 | 新版二进制包的 glibc 下限是实质障碍 |
| 默认工具 | Python 3.6.9、GCC 10.3、CMake 3.21.3、Git LFS 3.2.0 | 默认 Python 不能作为项目运行环境；CMake 低于项目所需 3.24 |
| Conda 等 | 当前 PATH 未发现 conda/mamba/micromamba；项目 `.local` 环境不存在 | 只能确认当前入口未准备，不代表全机没有其他用户环境 |
| 容器 | Docker 24.0.2、NVIDIA container CLI 1.17.3 可见 | 宿主只读 `docker info` 也遭 socket 权限拒绝；GPU runtime、Docker 数据目录尚未确认 |
| 视频工具 | `ffmpeg -version` 缺 `libxcb-xfixes.so.0`，启动失败 | 后续需要独立可用的视频编码/解码环境；本轮未修复 |

## 3. 不能原样搬运的兼容性

**R1 的原 TensorRT 10.13.3 不支持 V100。** NVIDIA 的版本说明明确 Volta 在 10.5 移除；10.4 是可调查的旧版本候选。还需核对 Ubuntu/动态库、SONIC C++ API、插件、ONNX 算子并重新构建目标卡 engine，不能把降版本直接记为通过。[NVIDIA 10.4 说明](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/release-notes-10/10.4.0.html)、[10.4 支持矩阵](https://docs.nvidia.com/deeplearning/tensorrt/archives/tensorrt-1040/pdf/TensorRT-Support-Matrix-Guide.pdf)。

**Torch 需要同时满足 GPU 架构与系统 ABI。** 原机 handoff 读取的 R1 `2.7.1+cu128` 编译元数据不含 `sm_70`，R2 `2.10.0+cu128` 含 `sm_70`；这是原机证据，本机没有安装这两套包。含架构标志仍不能证明 GEM-X/SOMA/Warp 能运行。部分新 Linux wheel 要求 glibc ≥2.28，本机为 2.27；单独创建 Conda 环境不自动升级宿主 glibc。[PyTorch 构建平台说明](https://dev-discuss.pytorch.org/t/pytorch-linux-wheels-switching-to-new-wheel-build-platform-manylinux-2-28-on-november-12-2024/2581)。

**驱动 530 不是“所有 cu128 都必然失败”的充分理由。** CUDA 12.x 存在 minor-version compatibility，但受新功能、PTX JIT 等限制；应检查选定包及实际内核，不能仅凭 `nvidia-smi` 的 12.1 标签判兼容。[NVIDIA 兼容说明](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)。

**V100 也不能照搬依赖新 GPU 内核的研究栈。** 例如 FlashAttention-2 的 CUDA 路径要求 Ampere/Ada/Hopper。需要逐模块确认可用 attention、精度和编译目标，并重新验证数值；32GB 显存不能替代架构支持。[官方仓库](https://github.com/Dao-AILab/flash-attention)。

候选路径是在不修改驱动/系统的前提下，使用支持 Volta 的独立用户态环境；需要更现代 glibc 时，可研究获准容器或兼容旧 ABI 的版本组合。当前 Docker 权限未解决，容器也不会升级宿主驱动或 GPU 架构，因此本轮不选定“已经可用”的安装配方。

## 4. 独立配置与资产清单

| 类别 | 尚缺内容 | 后续放行依据 |
| --- | --- | --- |
| 源码 | 子模块、真实 LFS 文件、原机未上传改动核查 | 固定提交、补丁和文件哈希一致；不覆盖人工修改 |
| R1 控制环境 | 独立 Python/兼容 Torch、MuJoCo、TensorRT/ORT C++、DDS/Unitree SDK、编译工具 | 导入/动态链接、CUDA 数值、通信、原 5 动作 × 2 次的目标机复验分别记录 |
| R2 提取环境 | GEM-X/SOMA 等独立依赖，FFmpeg，兼容 GPU 扩展 | 各阶段实际输出、完整时间轴、控制和录像回归；未用 R1 passed 替代 |
| 原项目资产 | SONIC 原始权重/ONNX 与匹配 observation；G1 LFS；GEM-X/SOMA/SMPL 等 | 本机从获准来源独立准备，遵守模型条款；记录 SHA、来源、版本，不复制旧 Conda 前缀/engine |
| R4 感知资产 | 手模型 MANO 等许可资产，手姿态、分割、深度、物体重建/跟踪权重 | 按选定方法逐项核对许可和架构；没有通用的一份“全部模型包” |
| R4 执行底座 | 选定灵巧手的 URDF/MJCF、关节/传动/接触定义、动作接口及控制器 | 手指级物理闭环验收；现有身体模仿接口不是已验收的灵巧手策略 |
| 数据与审计 | 新数据划分、资产来源、真值隔离、服务器运行身份 | 新 manifest/owner/boot/设备配置；原 R2 五条保留视频仍标为已使用 |

建议代码继续独立放在当前仓库，环境/模型/数据/缓存放入另一个获准数据目录，例如 `/home/junqiy/projects/humanmimic-data/`，分别建立 `envs/ models/ sources/ cache/ tmp/ runs/`。**该目录只是布局建议，本轮没有创建、预留配额或下载资产。** 安装前按实际所选模型估算峰值下载、解压、构建与结果占用；不要直接把多个百 GB 数据集全集放进系统盘。

现有脚本仍检查 `/mnt/c`、`/mnt/d`、owner marker、旧 boot 与二进制/GPU 身份。以后需新建服务器配置和明确的迁移回归路径，不能靠伪造盘符、删除使用台账或修改冻结哈希绕过检查。本轮保留所有脚本、配置和既有 evidence 字节。

## 5. 后续顺序与验收边界

1. 用户核查原机未上传源码；当前资料已足以完成研究分析，不必等待资产同步才给结论。
2. 运行授权变化后，先解决独立用户态栈/容器权限选择和数据路径，再准备最小所需资产。继续遵守“不改系统驱动、不从零训练、不启计费资源”。
3. 新 R4 可先建立独立的灵巧手仿真与重建评价底座，不必把所有 R1/R2 重跑作为先决条件；如果调用 SONIC/G1 链路，则必须完成受影响的目标机复验。
4. 小样本开发后冻结手型、任务、输入模态、精度门槛、比较预算和未使用测试集，再开始完整对照。详见 [R4 研究报告](research-video-interaction.zh-CN.md)。

| 分项 | 本轮状态 |
| --- | --- |
| 远端改名、源码同步、硬件盘点、研究文档 | `passed`，仅相应准备工作 |
| 本机代码解析 / 编译 / 模型前向 | `awaiting_verification`；未执行源码运行验证 |
| 动画或实际状态回放 | `awaiting_verification`；本轮未运行 |
| 无界面物理控制、R1/R2 迁移验收、R4 能力 | `awaiting_verification`；未运行 |
| 现场相机 R3 | 用户明确本阶段跳过；历史未验收，不能标 `passed` |
| Docker 访问 / FFmpeg 启动 | `failed`；仅这两项检查失败，不等同 GPU 失效 |
| 原机未上传代码是否齐全 | `needs_input`；用户正在核查 |

新增计费资源支出为 0；未生成新的实验录像。原机验收及媒体位置继续见 [results](results.md)，不暗示它们已复制到本机。
