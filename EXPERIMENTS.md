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
| 2026-10-28 Asia/Shanghai | WSL 私有仓库 origin 与访问检查 | origin配置passed；git ls-remote认证失败退出128，缺HTTPS用户名，访问needs_input；gh未安装。远端HEAD仍b60a877，工作区状态未变，未pull/fetch或覆盖新增环境文件，未中断环境安装 | 远端聊天01a18200-e7fa-7063-8afc-d73f214619e9；远端`runs/github-publish-20261028/remote-git-access.json` | 两端origin一致，handoff未重试；后续在WSL完成Git认证并复查访问，不复制本机令牌 |

原预检JSON中的Mac路径是当时的历史位置。迁移到WSL后，第一条运行记录应产生新的目标环境证据，不能沿用旧路径作为当前运行位置。

## 2026-10-28 WSL 远程预检

- 预期：当前代理直接在迁移后的 WSL Git 目录执行；通过只读检查判定 GPU 驱动与部署前置条件，不安装依赖或使用保留测试集。
- 环境观察 `passed`：主机 zhen、Ubuntu 24.04.4/WSL2、Ryzen 9 7945HX（32 逻辑 CPU）、WSL 内存 15.23 GiB、Python 3.12.3；RTX 4060 Laptop 8188 MiB、驱动 596.49；CUDA `cuInit=0`，设备数 1。C/D 剩余约 67/179 GiB；WSL 虚拟磁盘剩余不是宿主实际容量。当前版本 `b60a87778838f35c0bb771a29991cb4ede685bb7`，运行前差异与预算配置 SHA256 已记录。
- 部署就绪 `failed`：固定的 SONIC 子模块未初始化，无 Python 源码；当前解释器缺少 pip、PyTorch、MuJoCo、NumPy 等，项目无虚拟环境，Git LFS 命令不可用。默认 exec 沙箱因缺少 bubblewrap 启动失败，通过获准的沙箱外执行完成预检，未修复系统。
- 分项运行：源码 AST `awaiting_verification`；动画回放 `awaiting_verification`；无界面物理仿真 `awaiting_verification`；现场相机 `needs_input`（无 `/dev/video*`）。WSLg 存在，但尚无渲染证据。R1–R4 均未通过功能验收。
- 进程名和 GPU 进程快照未见项目仿真或训练；未重复提交任务、未启动计费资源，新增云费用 0 美元；未使用调试或保留测试视频/布局，无录像。
- 决定 `keep`：保留预检证据，更新当前执行位置，后续初始化固定源码和资产并建立独立环境，再运行 R1 短时预检。本轮仅环境检查与报告，不推进安装。当前副本无旧 `runs/` 目录内容，不能声称已复核旧远端原始日志。
- 证据：`runs/preflight-20261028-174003-wsl/manifest.json`、`environment.json`、`command-evidence.json`、`results.json`。

## 2026-10-28 R1 conda 初步环境配置

- 预期：保持固定官方源码，在独立 conda 环境内满足 Python 3.10 的官方仿真依赖；目标 RTX 4060 能完成 CUDA 运算，G1 模型可加载、执行基础物理步进并离屏渲染。此预期不包含 SONIC 跟踪或稳定性验收。
- 实现 `passed`：项目内 Miniforge 26.9.4-1 的 SHA256 与官方校验一致；创建 `humanoid-r1`，安装 Python 3.10.22、torch 2.7.1+cu128、numpy 1.26.4、scipy 1.15.3、mujoco 3.3.7、pin 2.7.0、opencv-python 4.11.0.86、cyclonedds 0.10.2、gear_sonic 0.1.0、unitree_sdk2py 1.0.1 及配套工具。固定 SONIC 子模块 `45c03facbf848e0c743091b7d9c17952096ff908`，G1 模型 68 个文件已完整获取、记录 SHA256，无残留 LFS 指针，官方工作区无修改。
- 保留失败记录：GitHub API 未认证限流、通用 SHA256 地址 404，后改用官方带版本号校验文件成功；初次 conda 求解因无 CycloneDDS 0.10.2 失败，改从官方标签提交 `9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd` 构建 C 库到环境前缀，未放宽 Unitree Python 固定版本。安装后的 LFS 本地过滤器改为环境内绝对路径，使未激活环境时 Git 也可正常读取工作区。原始失败日志未覆盖。
- 源码解析 `passed`：五个 R1 入口在 conda Python 3.10 中 AST 解析通过；官方仿真入口导入及 `--help` 通过，未创建 DDS 通道。`pip check` 通过；conda explicit、pip freeze、pip 安装报告已保存。
- 目标硬件 CUDA 运算 `passed`：RTX 4060、torch CUDA 12.8，256×256 矩阵乘法与 CPU 结果最大绝对差 0.0001220703125，张量峰值分配 9306112 字节（不是全流程显存峰值）。
- 基础无界面物理引擎 `passed`：G1 URDF 43 自由度，MuJoCo 场景 50 qpos/49 qvel/43 执行器，开启重力与自由根部执行 200 步、仿真 0.4 秒，状态有限。未启用 SONIC 控制器，不报告未跌倒、RMSE 或完整动作成功。
- 离屏渲染 `passed`：生成 320×240 的 G1 静态 PNG，渲染器为 Mesa llvmpipe 软件渲染；EGL 有 `/dev/dri` 访问权限提示，GPU 图形加速 `awaiting_verification`。静态图不是动画或动作录像。动画回放、SONIC 闭环无界面验收均 `awaiting_verification`；现场相机 `needs_input`。
- 决定 `keep`：保留 conda 环境与激活/检查脚本、配置及 pip 锁定文件；未改系统 Python、驱动或 shell 启动文件。未使用调试/保留测试动作集，未启动计费资源，新增云费用 0 美元，无录像。
- 后续：补齐官方 TensorRT 10.13/CUDA C++ 开发依赖和控制器编译，获取默认策略权重及最小动作集，验证 loopback DDS 往返，然后进入 R1 10 秒闭环预检；本轮初步环境配置已完成，R1 功能验收仍未完成。
- 证据根目录：`runs/r1-conda-setup-20261028/`；摘要 `results.json`；环境实测 `smoke-01/environment-smoke.json`、`smoke-01.log`；静态图 `smoke-01/g1-offscreen.png`；精确版本 `conda-explicit.txt`、`pip-freeze.txt`；资产清单 `g1-assets-manifest.json`。

## 2026-10-28 R1 完整环境与一次闭环复现

- 本轮范围：用户要求完成 R1 完整环境并复现一次，输出实际状态、参考值、指标和录像；不改变 PLAN.md 五动作各两次的后续整体验收。修改前预期与版本已写入 `runs/r1-full-setup-20261028/manifest.json`，首次策略运行前固定 `configs/r1-evaluation.json`。
- 环境配置 `passed`：补齐 TensorRT 10.13.3.9 官方 C++ 包（官方 SHA256 验证）、CUDA 开发工具 12.8.93、ONNX Runtime C++ 1.22.0、Eigen 3.4 等。取得默认 SONIC 编码器/解码器/匹配配置、规划器及 `macarena_001__A545` 的全部 LFS CSV。控制器编译成功；初次缺少 NvOnnxParser.h 的编译失败保留，补齐同版本解析器开发包后通过。构建日志保留上游 picosha2 编译器警告，未隐藏警告或修改策略。
- 传输诊断与修复 `passed`：WSL lo 无多播标志，使用项目内显式单播发现；原生 UDP 大小诊断显示 256/1200 字节可收，2180/8192 字节收不到，DDS 改用 1200 字节消息/1024 字节分片后合成 LowState 诊断通过。conda 旧式 RPATH 导致误选同名 C 库，改为 RUNPATH 并添加 SDK 配套库 SONAME 链接；Python 0.10.2 wheel 实际携带 C 0.11.0，改为源码绑定，Python/C++ 两端统一使用 SDK 的 C 0.10.2。自行构建 C 库的初始化异常、配置诊断、调用栈、失败消息和最终实际加载路径均保留；未改系统网络、驱动或系统 Python。相关证据在完整配置运行目录。
- 预检 01 `failed`：无 LowState 到达，未开始动作；检查活跃进程和日志后主动结束诊断，没有把观察超时当作进程失败。证据 `runs/r1-preflight-20261028-01/`。
- 预检 02 `failed`：通信修复后启用策略，但播放前跌倒；物理轨迹保留，没有自动复位。证据 `runs/r1-preflight-20261028-02/`。预检 03 `failed`：控制器准备好后才启动物理步进，释放支撑后仅靠初始化 PD 仍失稳；证据 `runs/r1-preflight-20261028-03/`。两次均无有效播放 RMSE，指标为 null，没有用目标值代替实际值。
- 预检 04 `passed`：控制器就绪后开始物理步进，PD 初始化完成后启动 SONIC，收到首个策略输出即释放弹力带，0.2 秒后播放；权重、动作、增益和评价标准保持一致。10 秒内 500 个播放样本，RMSE 0.1277503544 rad、未跌倒、播放期间无弹力带。证据 `runs/r1-preflight-20261028-04/`。
- 完整单次复现 `passed`：`runs/r1-reproduction-20261028-01/`，官方样例 Macarena，1375/1375 帧、名义时长 27.5 秒；全动作 29 关节 RMSE **0.1361738375518422 rad**，低于预定 0.35 rad。未跌倒或跟踪中止，最低根部高度 0.6564058708 m，未持续超过预定倾斜或非足底接触门槛。自由根部、重力、接触、扭矩控制启用，播放期间弹力带关闭；没有实际状态覆写或自动复位。控制器日志确认动作 completed，双方退出码均为 0。
- 全量指标复核 `passed`：在线 ZMQ 收到 1374 个播放样本，收尾缺少索引 1385；原生 CSV 保留全部 1375 个。依据 StateLogger 实现确认 q.csv 已是恢复偏置后的实际 MuJoCo 顺序，未重复变换。与全部共同在线样本对照，实际值最大差 5e-10 rad、参考值最大差 5e-6 rad；全量参考值逐帧匹配原始动作。`full-sample-metrics.json` 使用完整原生数据，同一控制时刻计算，没有拟合时间平移或放宽门槛；原在线指标 `metrics.json` 保留。
- 录像与物理时间审计 `passed`：实际物理时间连续，以 0.005 秒递增，无复位跳变；执行结束后由实际 qpos 轨迹离屏渲染 H.264、640×360、25 fps、688 帧、27.52 秒录像，完整解码和首中尾画面通过。渲染为 llvmpipe 软件路径；GPU 图形加速仍 `awaiting_verification`，现场相机 `needs_input`。动画/轨迹回放与实际闭环物理执行分开记录。
- 决定 `keep`：保留配置、源码补丁、启动工具、四轮预检、完整运行、录像和审计。默认权重和控制逻辑不变，局部补丁仅允许 lo 的显式 DDS 配置入口。未使用保留测试集、真机、训练或计费资源，新增云费用 0 美元；全流程峰值显存未采样，不填写为零。
- 最终文档同步：曾因 Goal 暂停而未完成，用户恢复后只核对现有进程与证据、补全文档和最终交付审计，未重复启动已完成实验。本次单动作目标通过，PLAN.md 的五动作双次验收和 R2–R4 保持待完成。
- 主要证据：完整环境 `runs/r1-full-setup-20261028/results.json`、`conda-explicit-full.txt`、`pip-freeze-full.txt`、`models-and-reference-manifest.json`、`dds-final-runtime.json`；运行报告 `runs/r1-reproduction-20261028-01/REPORT.md`；全量指标 `full-sample-metrics.json`；原始状态 `actual-state.npz`；实际值/参考值 `full-sample-tracking.npz`；录像 `actual-execution.mp4`；独立审计 `completion-audit.json`、`independent-artifact-audit.json`。

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


## 2026-10-28 R1 归档、Git 同步与下一轮准备

- 预期：保留已验证环境和单动作结果，将版本化内容推送私有仓库；合并两端既有历史，固定下一轮五动作各两次的输入、规则和入口，不把准备成功当作五动作通过。原始预期与版本在 `runs/r1-github-handoff-20261028/preparation.json`。
- 仓库核查：`LyrineYang/humanoid-demo` 已存在且为 Private，复用已有仓库；远程 `d515531` 比 WSL 基线多三个文档提交，先提交本轮 R1 工作再合并，人工解决文档冲突，保留全部远程历史实验行与当前真实 R1 状态。没有强推或覆盖远程历史。gh 首次把不可用本地代理导致的请求错误显示为登录无效，临时移除本次命令的代理变量后登录与 fetch 均通过；没有修改持久代理、复制令牌或关闭证书验证。
- 输入准备 `passed`：固定五动作 Macarena、dance in da party、squat、walking quip 360、forward lunge 官方镜像样例，分别 1375/497/424/455/399 帧，全部八类文件与上游 Git/LFS 对象逐项核对；CSV 表头不计入有效帧数。清单 `configs/r1-suite.json`，目标仍为同一 RTX 4060、默认策略、控制器、0.35 rad 和稳定性规则。官方样例/调试角色不变，未使用保留测试集。
- 工具实现：新增输入准备与十试次汇总，单动作运行器只增加冻结配置入口和参考完整性校验，物理步进、策略、增益、启动时序及评价门槛不变。完整试次串行使用 DDS domain 0；失败保留并继续记录，审计失败显式标记；全部十次完成后至少四个动作两次均通过才验收。既有 Macarena 演示/工具验证不替换固定试次。
- 工具检查 `passed`：AST、生成的 Bash 语法、pip check；故意损坏资产哈希会拒绝生成命令；十试次尚未运行时正确输出 awaiting_verification 与全部十个 pending 结果。干净上游文件可应用补丁，应用后与当前运行源码逐字节一致。证据 `runs/r1-github-handoff-20261028/` 与 `runs/r1-suite-ready-20261028-04/`。
- 版本化摘要 `evidence/r1-baseline-20261028.json` 保存前阶段完整指标、环境和产物哈希；新加 conda 精确清单及原生 SDK 官方下载/校验配置。环境、权重、原始轨迹、录像和账号配置保持忽略，不提交 Git；子模块仍固定官方提交，修改以可审查补丁表示。新增云费用 0 美元，未训练、连接真机或更改系统驱动。
- 新配置入口回归 `passed`：`runs/r1-configurable-runner-20261028-01/`，1375/1375 帧，RMSE **0.13754351595441291 rad**，未跌倒；H.264 640×360、25 fps、688 帧、27.52 秒录像完整解码通过。实际单次结果交给汇总工具，正确识别一试次通过、九试次未运行、零动作双次通过，整体保持 awaiting_verification。该验证目录不计入已冻结的下一轮十试次。证据 `configurable-runner-verification.json` 与 `partial-suite-auditor.log`。
- Git 发布与独立克隆 `passed`：R1 配置与下一轮准备提交 `73bfdef` 已推送私有 main；从 GitHub 新克隆确认同一提交、29 个版本化文件、固定 SONIC gitlink、脚本 AST/配置 JSON 与干净父工作区。原始输出 `runs/r1-github-handoff-20261028/publication-audit.json`。父仓库没有未提交业务文件；本机子模块保留已应用的 DDS 补丁，补丁内容已版本化且可从干净上游复建。
- 批次证据保护 `passed`：生成入口会在首次试次前检查全部目标目录和日志；任一既有证据会使整批拒绝运行。用最后一试次的既有日志作对照，确认日志字节保留且第一试次未启动；启动/审计失败显式记录，避免误标未运行。最终十试次准备目录 `runs/r1-suite-ready-20261028-04/`，没有执行整批；云费用仍为 0 美元。


## 2026-10-28 R1 五动作双次整批验收

- 修改/运行前预期：用户明确要求直接推进整批验收；复核输入哈希、依赖、GPU、可用内存/磁盘及活跃任务后，执行固定五动作各两次，至少四个动作两次均通过原门槛才标记 R1 passed。完整版本、脚本快照、配置、硬件与预期记录在 `runs/r1-suite-acceptance-20261028-01/execution-manifest.json`。
- 预检 `passed`：无活跃控制器，pip check 与所有冻结输入哈希通过；目标仍为 RTX 4060 Laptop，当前驱动 621.01，较历史单动作记录 596.49 有变化，未由代理更改。批内固定当前环境；不将跨驱动指标差异归因于策略改进。整批运行状态 awaiting_verification，未使用保留测试集，新增云费用 0 美元。
- 中途结果：Macarena 试次 01 `passed`，1375/1375 帧，全量 RMSE 0.13471399851106688 rad，未跌倒且录像解码通过；试次 02 `failed`，751 个播放 CSV 样本后跌倒，最低根部 0.19487218898 m、持续过度倾斜约 0.873 s，动作未完成。局部在线 RMSE 0.29877 rad 不能替代完整动作成功，未重跑替换或调参；整批仍在进行，证据在对应试次目录。
- 舞蹈试次 01 `failed`：实际跌倒，动作未完成；Macarena 与舞蹈均已有失败，故该固定批次不可能达到四动作双次通过。继续执行剩余试次以完整报告，不替换动作或放宽规则。运行跨过 Asia/Shanghai 的 2026-10-29 零点，保留开始于 10-28 的批次 ID。
- 2026-10-29 完整批次 `failed`：十次全部结束，3 passed / 7 failed，0/5 动作双次通过（要求至少 4）。通过项为 Macarena 01、squat 02、forward lunge 02，全量 RMSE 分别 0.134714、0.141099、0.139410 rad；其余均实际跌倒，完整指标为 null，局部指标单独保留。独立审计通过：成功试次参考逐帧一致，十试次物理时间连续且无复位。运行过程中所有冻结输入及脚本哈希保持不变。完整汇总 `evidence/r1-batch-20261029.json` 和批次 `suite-audit.json`。
- 计时修复前预期：播放期间物理时间/墙钟比例实测 0.819–0.971，官方循环逐步相对 sleep 会累积调度超时；参考/策略仍墙钟 50 Hz。拟仅改仿真节拍为绝对截止时间，保持物理步长、官方 sim_step/更新、动作/策略/门槛不变，在新诊断目录验证失败动作。假设未证实前不声称其为跌倒原因；原批次不撤回或覆盖。预期 `runs/r1-pacing-repair-20261029/hypothesis.json`。
- 绝对节拍诊断 `passed`：仅修正仿真循环 deadline，原官方物理步进/辅助更新、0.005 s 步长、策略、增益、动作与门槛不变。舞蹈/深蹲/行走分别完整执行 497/424/455 帧，无跌倒，全量原生关节 RMSE 为 0.173689, 0.131657, 0.111301 rad；物理时间/墙钟恢复为约 1.000。参考逐帧一致，诊断无录像，不能作为正式试次。决定 keep，并在新目录重跑同一五动作×两次，不覆盖首轮失败。证据 `runs/r1-pacing-repair-20261029/`。
- 恢复时发现驱动实际已从 621.01 变为 617.42，未由代理修改；原第二轮保持 awaiting_verification（仅两个物理试次），不能合并当前版本余下八次后声称统一环境验收。恢复 shell 未在断言失败后停止，离屏重渲染继续并覆盖原未完成录像/编码日志；原始实际轨迹、控制/参考日志、在线包、指标未被渲染修改，已记录各自 SHA256。修正后续命令为失败即停止，决定在新目录以当前固定驱动完整重验十次。证据 `runs/r1-suite-acceptance-20261029-02/interruption-recovery.json`。
- 中断恢复入口保护验证 `passed`：构造不同驱动清单时，在生成锁/日志或修改试次前拒绝，原清单哈希和目录内容不变；新批次真实环境检查通过。第二轮第02次离屏录像补全和解码审计通过，物理数据 SHA256 保持不变，仍不计入第三轮。第三轮 `runs/r1-suite-acceptance-20261029-03/` 当前驱动617.42，使用检查点入口串行完整执行十次，门槛与清单不变。
- 2026-10-29 当前统一驱动617.42正式整批 `passed`：五动作各两次全部完成，10/10通过、5/5动作双次通过（门槛至少4/5），6300/6300原生控制样本；无跌倒/跟踪中止，完整29关节RMSE范围0.1087518261–0.1751706371rad，原≤0.35门槛不变。逐动作两次：Macarena 0.133782/0.134089，dance 0.172700/0.175171，squat 0.134192/0.131211，walking 0.109179/0.108752，lunge 0.134148/0.135739rad。
- 最终独立审计 `passed`：全部原始参考逐帧一致、物理时间连续0.005s无复位、播放弹力带关闭且重力/接触/自由根部/控制器启用，十段实际轨迹录像完整解码；物理时间/墙钟0.999949–1.000045。源/配置/策略/当前GPU版本保持冻结。已完成批次再次调用恢复入口后，物理启动数仍为10，全部已归档物理产物哈希不变。原失败批次和跨驱动中断批次继续保留/排除，不降低标准或混算。报告 `runs/r1-suite-acceptance-20261029-03/REPORT.md`、results.json、suite-audit.json、independent-trajectory-audit.json、completed-resume-verification.json；Git摘要 `evidence/r1-acceptance-20261029.json`。
- 决定 keep：保留绝对节拍修复、恢复入口和所有成功/失败证据，R1工程验收通过，下一阶段推进R2。未使用保留测试集、真机、训练或计费资源，云费用0美元；源码、闭环无界面与实际轨迹回放passed，GPU图形/窗口awaiting_verification，现场相机needs_input。整个四阶段项目未完成。
