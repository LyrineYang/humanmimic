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

- 2026-10-29 R2交付约定补充：用户明确要求项目包含生成结果和demo。修改前预期为保持已定视频→GEM-X→SOMA/SMPL→SONIC路线与至少4/5保留视频门槛，补齐每阶段可复跑入口/真实结果包/demo；R2默认本地一键离线入口、缓存和指标报告、原视频—骨架—实际仿真三路对照MP4。文档检查passed；R2实现/运行仍awaiting_verification，未启动安装、推理、视频测试或云计费任务。视频来源与额外网页偏好只需简短确认。证据 `runs/r2-deliverables-plan-20261029/results.json`。

- 2026-10-30 R2来源/demo规格确认：用户明确普通YouTube单目/K-pop视频作为主要检验对象，可由代理搜索相关数据集；demo同步展示原片、动作提取可视化与机器人实际执行，保留中间结果，源视频内容无需剪辑。修改前预期为保持既定路线及5调试/5保留、至少4/5门槛，只完善输入/交付规格。已核对AIST++、BRACE、FineDance官方说明并找到YouTube候选；候选未下载、未视觉验明或用于提取，不冒充冻结测试清单。AIST只用单路RGB输入，BRACE复杂地面技巧单独作挑战，不用现成标注代替提取。文档与来源调研passed；R2实现/运行awaiting_verification；无新增安装、模型推理或云费用。证据 `runs/r2-source-demo-20261030/results.json`、`source-candidates.json`。

- 2026-10-30 R2 Goal审核稿与资源预检：用户要求先审核下一阶段命令，未启动Goal/安装/推理或计费。预期为复用R1、本机资源与现有D盘空间，完整实现R2及5调试/5保留验收和三路demo。RO检查确认4060 8188MiB、当时约1936MiB占用，WSL约15GiB；C约余11GiB、D约余263GiB，WSL虚拟盘位于C。核对OpenAI官方Goal文档及GEM-X官方安装/推理/配置说明，记录新版API/依赖与固定桥接的适配风险，不将其他模型的显存数字套用于GEM-X。建议串行离线提取→缓存释放→控制→渲染，先实测再判断8GB能力；资源不足保持原验收并继续可行工作，云计费需另行授权。文档/资源检查passed，R2实现与运行awaiting_verification。证据 `runs/r2-goal-review-20261030/results.json` 和 goal-draft.txt。


## 2026-10-30 R2 串行可行性、时间与存储成本审核

- 修改前预期：用户请求估计4060串行方案、时间/存储成本并审核prompt；仅作只读硬件/源码/模型元数据核对与文档修订，不把资源评估Goal当作R2执行授权。预期 `runs/r2-resource-estimate-20261030/preparation.json`。
- 评估证据 `passed`：当前GPU8188MiB、约5.8GiB空闲，WSL15.2GiB，C约10.2GiB/D约262.2GiB；未发现活跃提取/控制/渲染任务。官方新分支按模型分阶段释放、ViTPose要求FP32且带翻转；三个主要权重合计7,114,371,056B。旧SONIC桥接API与新版不同，最终运行版本尚未选定，未将第三方显存传闻或文件体积当峰值保证。
- 估算：10段平均30秒完整原片，假设有效提取2–10fps；首demo6–16工程小时，稳定后一轮1.5–5小时，R2含工程工作2–5工作日。十段已有R1日志观察软件机器人渲染3.0–3.4fps，累计5分钟原片约37–42分钟；人体渲染/GEM-X速度尚未验证。CPU慢速情景约4–16小时/轮，非测得性能。新增空间规划40–80GiB，建议D预留100GiB；单条完整预检及最长调试片需更新估算。预算不是截止期限或成功承诺。
- 决定 `keep` 文档修订：STARTUP_PROMPT审核稿加入D独立conda/缓存/TMPDIR/结果布局、低磁盘保护建议、按需解码、完整数值中间结果、分阶段profile和禁止超时重提任务；修正旧启动提示中“缩短视频”和R2先并行的表述，保持完整源片与R3实时门槛分开。原5调试/5保留、至少4/5稳定完成及所有失败保留要求不变。
- 分项：资源调研/估算文档passed；R2代码实现、GEM-X本机显存/吞吐、闭环与demo均awaiting_verification；现场相机needs_input。未下载安装大模型、新建环境、运行推理/仿真、写D盘、连接真机、训练或使用云计费，新增云费用0美元。当前资源评估目标完成不等于R2执行Goal已启动。
- 证据：`runs/r2-resource-estimate-20261030/REPORT.md`、results.json、gem-x-hf-tree.json、soma-x-hf-tree.json、official-source-excerpts.json、r1-render-observations.json；小型版本化摘要 `evidence/r2-resource-estimate-20261030.json`。下一步待用户审核执行稿后按原路线做本机完整单视频资源预检。


## 2026-10-30 R2执行授权与D盘兼容预检

- 用户批准更新后Goal：本机4060、D独立conda及100GiB规划；完整单视频预检后按实测预算继续整批，保留中间结果/三路demo，暂不使用计费云。Goal统一在STARTUP_PROMPT.md，执行状态在PLAN.md，不新增记忆文件。
- 修改前预期与版本策略见 runs/r2-setup-20261030-01/manifest.json：D盘不同于WSL根所在盘不应阻止Linux/CUDA运行，但需实测DrvFS链接、执行、导入和I/O。
- D基础探针passed：ELF执行、相对符号链接执行、跨根目录链接读取、同D硬链接均通过；大小写不敏感，后续检查安装路径和导入冲突。64MiB有界探针顺序写163MiB/s、缓存读207MiB/s；300个512字节文件写1.04s，未当作冷读模型性能。临时测试数据已移除，探针代码/日志与结果保留在运行目录。
- 决定keep D专用目录 /mnt/d/humanoid-demo-r2，100GiB为项目规划上界并监测宿主空闲，不创建100GiB占位文件；独立prefix/包缓存/TMPDIR/模型/新结果都在D。原R1环境和补丁保留，新增云费用0。conda/CUDA、GEM-X与全链路仍awaiting_verification。


## 2026-10-31 R2中断恢复、路径核对与桥接实现

- 前一轮为progress：D基础兼容/conda运行通过，固定源码并启动依赖/模型下载。恢复时旧句柄21142/63284缺失，进程检查无相关任务；保留469,762,048B模型分片和原安装日志，不将观察超时当失败。此前审批服务报告应用网络权限撤销；本次正常审批访问已恢复，没有绕过检查。恢复记录 runs/r2-setup-20261030-01/interruption-20261031.json。
- 当前资源：驱动仍617.42；GPU空闲约7GiB。C盘曾仅余3.8GiB，用户确认自行释放后复查约21GiB，满足原10GiB保护线。新环境、权重、conda/pip/HF/torch缓存、TMPDIR及新结果逐项确认在D；C保护线是Windows/WSL运行余量，不是额外下载额度，源码仓库仍在WSL根文件系统。
- 资产校验passed：按固定HF版本恢复完整下载，所有公开LFS SHA256一致，下载结果 /mnt/d/humanoid-demo-r2/runs/asset-download-20261030/results.json。恢复后网络约10–12MiB/s，与旧0.5MiB/s情况分开记录。
- 代码实现：新增分阶段提取缓存/资源采样、SOMA新版几何到官方SONIC转换适配，以及复用R1仿真工作进程的Protocol-v3缓存物理回放入口。AST检查passed；四帧完整消息与官方pack_pose_message逐字节一致passed，修正初版header count与帧数混淆；真实SOMA转换、CUDA推理和物理运行尚未验证。
- 单独下载的Mixkit51314完整原片约21.94s、526帧；抽帧发现末段脚部出框，不进入基本全身可见门槛或YouTube保留集，只保留为辅助挑战候选，尚未提取。仍继续筛选普通YouTube/K-pop来源，不替换最终普通视频验收。
- D环境PyTorch/GEM-X安装仍在同一任务35644进行；修正全局PYTHONPATH只含GEM-X，SONIC helper仅转换时显式加入，避免pip将R1源码metadata误识别为R2安装包。未升级R1，未用保留集、真机、训练或计费云，费用0。最新分项状态见 runs/r2-setup-20261030-01/progress-20261031.json。


## 2026-10-31 R2独立环境通过并启动完整视频预检

- D环境CUDA/依赖分项passed：PyTorch2.10.0+cu128、transformers5.3.0、py-soma-x0.3.3、numpy2.2.6、scipy1.15.3；矩阵512x512最大绝对差4.1962e-5。首次Torch导入26.675s，整套依赖导入144.824s，未将冷启动时间当作模型逐帧吞吐。隔离后的pip check通过，R1源metadata不再混入R2。原安装任务末尾旧PYTHONPATH导致的pip check失败保留，无需重装已正确安装的依赖。
- SOMA接口首次中性姿态检查failed：旧解析使用110关节原始rig名称给77关节公开输出索引，index84越界。按SOMA官方public_joint_names/public_joint_indices核对公开77布局，与GEM native77名称逐项一致后修复适配；相同真实资产、相同官方SONIC坐标数学重验passed。初次失败与修正结果都保留，未以截断索引/默认零值掩盖错误。
- 首条原始27.933s、838帧的普通YouTube单人舞蹈原片QqvZAUEOrAQ进入端到端调试预检，完整源文件SHA047574246202c1e6f80b7e7ed46ac15c5968debe37fc06730adf9e41dab13213。原片约20帧首黑和20帧尾黑保留并要求记录缺失/填补；不是保留测试，未把带多画面或双人的候选混入基本单人门槛。源片预处理已完成，原始PTS与30Hz映射存档，当前正在CPU人物检测阶段。
- 启动前预期见video-preflight-expectation-20261031.json；初始进程检查误匹配启动器文本，在模型执行前被纠正，未重复启动已活跃任务。已保存与执行哈希一致的源码快照。预处理耗时141.59s，后续峰值显存/耗时、转换、物理/三路demo仍awaiting_verification；不把准备或接口通过等同于R2完成。
- 本轮仍仅本机4060/CPU，无训练、真机、驱动更改或计费云。R1源码/默认策略与物理步进保留，新原生TensorRT缓存也安排到D，所用SONIC权重与已通过R1逐项SHA一致后才执行。证据根runs/r2-setup-20261030-01/及runs/r2-preflight-youtube-QqvZAUEOrAQ-20261031-01/，Git摘要evidence/r2-setup-20261031.json。

## 2026-10-31 R2 首片中断核查、恢复与身体评估工具

- 修改前预期：保留首片所有中间结果，确认真实进程停止后才恢复；核对原片/源码/缓存身份，拒绝重复进程和变化后的冻结源码，只重跑未完成阶段。身体误差以实际记录qpos离线FK和提取参考为准，核对原生消费帧与控制时钟，不将全零协议字段当目标，不拟合时间平移。预期见 `runs/r2-setup-20261030-01/recovery-evaluator-expectation-20261031.json`。
- 新运行证据 `passed`（仅分阶段）：完整838帧预处理141.5886s、CPU检测465.5798s、特征243.3696s；BodyPose框架峰值分配3,675,342,848B、保留3,737,124,864B，系统含桌面峰值5041MiB。该阶段在本机8GB显卡完成，不能外推Motion或全链路。2D姿态attempt01最后采样约200.98s，未生成完成标记或错误；21:47核实旧终端13936缺失、PID32019不存在、本次WSL启动21:37，原尝试按外部中断保留为awaiting_verification，没有证据判为OOM或模型失败。
- 恢复保护 `passed`：原片和三项完成缓存、12个冻结源码/配置身份一致；活跃控制器模拟进程和变化后的冻结源码均被拒绝，未启动推理。`resume-r2-demo.py`在本机空闲显存≥6144MiB持续15秒后才调用既有入口，最长观察1h，每次记录单独JSON/日志。当前GPU另有Windows游戏负载，空闲约2–3GiB，恢复等待进程真实存活；代理未停止任何用户应用。证据 `recovery-guard-check-20261031.json`，首片 `interruption-20261031-2147.json`、`resume-attempt-01.json`。完成缓存不重复计算，姿态恢复使用attempt02。
- 身体/时序工具验证 `passed`：实现14项肢体角度/垂直与外展比例、固定原片事件窗口、原生SMPL/四元数逐帧前缀身份与日志index/时钟核对。解析几何旋转/平移/尺度不变性、已知0.2s事件延迟检出、跳帧/四元数更改/日志index缺口拒绝、部分事件窗口失败均通过；真实已验收R1的9个实际qpos离线FK生成12个具名人体对应锚点，全部有限。CLI完整报告检查通过：缺少关键事件或物理证据为awaiting_verification，参考身份损坏为failed。合成参考/复用R1状态只用于工具验证，不计R2通过；实际R2身体/时间/事件仍awaiting_verification。证据 `/mnt/d/humanoid-demo-r2/runs/r2-evaluator-check-20261031-01/`。
- 环境版本归档 `passed`：保存conda精确URL包清单和pip锁定清单到configs，将本机构建路径替换为实际metadata版本、GEM-X使用固定子模块editable路径；未安装或升级任何包，未做新机重装验收。证据 `environment-lock-export-20261031.json`。
- 来源准备：新增8条完整YouTube源（10.75–44.22s）与来源/SHA/原音轨/等比例全时间轴预览；可视筛选发现6条多人、镜头切换/近景或明显标题/尾屏，不混入基本单人门槛。2条深蹲/原地踏步保留为待密集检查候选，继续寻找普通K-pop/上肢来源。此为来源筛选，无动作推理、无保留测试使用，未按模型成功率换样；所有源和排除理由存D。证据 `/mnt/d/humanoid-demo-r2/sources/source-qualification-20261031-2210-review.json`。
- 决定 keep：保留分阶段缓存、恢复入口和独立评估工具，GPU有余量后续跑原首片，再据完整实测更新预算并推进原5调试/5保留验收。R2物理、三路demo、冻结保留集和整批仍awaiting_verification；云费用0、R1/驱动/策略/验收标准未改。

## 2026-11-01 R2 恢复执行与密集来源检查

- 用户确认已退出Windows游戏并要求继续。01:20实查旧等待PID不存在、本次WSL boot_id已变化，原姿态attempt01及前三项完成缓存仍在；显卡驱动617.42、空闲约5962MiB，C/D保护检查通过。恢复前保存独立观察与资源预期：采用5120MiB空闲启动余量，已测BodyPose框架保留约3564MiB、仍留约1.5GiB额外余量；这不是降低动作/物理验收，FP32/批量1/权重/控制频率不变。再次核对冻结源码和缓存后启动同一首片姿态attempt02，未重跑前三阶段。恢复观察 `runs/r2-preflight-youtube-QqvZAUEOrAQ-20261031-01/resume-observation-20261101-0120.json`、resume-attempt-02和独立阶段资源日志；目前仍awaiting_verification。
- 来源工具首次运行 `failed`：全帧解码与首条预览完成后，NumPy int64索引不能JSON序列化；保存失败记录和原预览，改为Python int，在新目录完整重跑。修复后7条完整原片全解码/元数据/哈希/20帧等比例预览 `passed`，但不代表人体提取通过。4条候选为Cupid单人舞蹈、固定健身房臂环绕、户外踏步和深蹲；3条因切镜/近景裁脚或相机平移排除，密集检查纠正了初筛踏步候选的固定相机判断。未按模型结果筛选，全部源和排除证据保留；数据划分尚未冻结，保留测试推理未使用。原失败 `runs/r2-source-review-20261031-02/failure.json`，成功及人工复核 `runs/r2-source-review-20261031-03/results.json`、visual-review.json。
- 01:40复核恢复中断：原姿态attempt02进程消失，WSL启动变为01:39；Windows事件41/6008记录非正常重启，前一Linux boot无OOM kill，末尾dxg ioctl -22记录不能独立证明驱动根因。末尾采样系统显存约7804MiB/可用RAM约7.8GB，无Python模型异常输出，按主机中断保留。预期/证据首片 `interruption-20261101-0140.json`、previous-boot-kernel-20261101.log、windows-reboot-events-20261101.txt。
- 独立检查点生产器修改前预期：保持所有原冻结源码、权重、crop、FP32/batch1和翻转增广不变，只按官方独立图像batch循环分块；实际两帧整段与分帧输出必须逐元素相同，每块记录SHA/源码/配置/显存，全部838帧完成才产主入口完成标记。预期首片 `pose2d-checkpoint-expectation.json`。真实等价检查 `passed`，缓存identity绑定输入/归一化视频/框/权重/发布版/原辅助源码，生产器副本保留。
- 分块首轮再遇主机中断：本次WSL启动01:55，旧worker15402不存在。13块共416帧完整元数据与tensor SHA逐项 `passed`；框架峰值分配3,540,864,000B、保留3,642,753,024B，已归档系统显存4360–4362MiB，温度采样最高87°C。中断后第416:448及448:480块元数据和progress全为NUL；保留为damaged原件，未将无证明的64帧算入完成。显存仍有约3.5GiB时也出现异常重启，不能把本轮解释成8GB显存不足，也不能确认热/供电/驱动根因。审计 `interruption-checkpoint-audit-20261101-0157.json`。
- 决定修正恢复方式：保留原数值生产器身份，另增加显式记录源码的持久化包装，只替换元数据writer为fsync+rename，每次最多3个32帧新块，开算前温度<60°C并保留资源等待。文件写入/读回检查 `passed`，未模拟断电；运行/完整姿态仍awaiting_verification，未改系统驱动/功耗或推理质量。用户确认可能为电脑自行重启，要求再试；随后明确先推进本机，将来由用户连接服务器。未启动云计费或连接未知服务器。
- 原片调试关键事件准备 `passed`（标注本身）：在查看提取3D/实际执行前，依据原视频7.2/9.9/14.4/16.2/18.9/27.0s画面记录6个有固定窗口/方向的事件，原片SHA匹配；`configs/r2-debug-events-QqvZAUEOrAQ.json`。这些不是模型事件验收结果。新增完整源密集筛选中，固定机位站姿转体与反向弓步为候选，三条躯干/弓步来源及一条镜像舞蹈因切镜、近景或多人排除；所有原片/证据保留，未用保留集推理。`runs/r2-source-review-20261101-01/`、`runs/r2-source-review-20261101-02/`。
- 冷却/持久化包装首次有界运行 `passed`（仅短批次执行）：416→512帧新增三块，正常返回3并释放GPU，没有主机重启；全片仍awaiting_verification。框架峰值仍3,540,864,000B/3,642,753,024B，记录的新增块均使用原官方数值生产器；新代码只处理调度和metadata写入，完整源码身份与旧块证据保留。`pose2d-cool-bounded-attempt-01.*`、对应durable-recovery记录。
- 扩展冷却分组前预期：最多4组×3个块，组间释放GPU权重、至少休息30s且温度<55°C，120s不满足就返回3，不重写未完成为passed。CPU模拟producer/clock验证 `passed`：完成立即停止、休息累计时长、过热等待超时、最多4组边界；未初始化CUDA，不当作硬件运行结果。`runs/r2-setup-20261030-01/cooling-cohort-check-20261101.json`。
- 分组续算真实观察：首组512→608帧，组间framework分配降为9,756,672B、系统空闲6608MiB，约75s后温度54°C，再进入下一组；这是权重释放/冷却的实证，尚非完整姿态通过。`pose2d-cooled-cohorts-attempt-01.*`及durable-recovery-1793470318448003548.json。源模型/FP32/增广/50Hz控制/验收不变。提交8ee55cb已推到原私有仓库R2分支，未上传模型、视频或原始日志，没有创建PR或改动main。

## 2026-11-01 R2 首片完整预检通过与原生时钟修正

- 预期沿用原片838帧/无剪辑、官方FP32 batch1/翻转增广、相同策略与物理判据；完整结果才标记通过。冷却分组续算512→838完成，27块全部SHA/形状/有限值及拼接审计通过；原keypoints2d SHA180ccc108a698836740d54cbe0686257238426c5f61e3ed2eaa6b668419bb7ae。camera/motion/postprocess/convert依次完成，转换抽帧与官方函数最大差约2.06e-7m，所有中间数据保留。决定keep。
- 首次物理失败保留：strict-shell调用conda hook时读取未定义NVCC_PREPEND_FLAGS；activate-r1只在conda activate内临时关闭nounset并恢复调用方状态，正常/strict激活环境一致检查passed。30秒初始化截止时模拟器刚就绪，原physical/失败不覆写；在新physical-attempt-02仅将初始化等待延长120秒，策略/控制/稳定性门槛不变。
- 真实完整物理 passed：1397/1397源样本消费，无跌倒，最低根高0.521982m；重力/接触/自由根部/控制启用，源期间无弹力带，无qpos/qvel覆写。实际状态SHA f89b0b88b5025b2a721e54c5babf0d67b63d48dfda49c54002e821b45cfebce8。6个提前按源片标注的事件方向/顺序全部passed，相对提取的峰值时间差[0,.24,.14,.04,-.08,-.14]s；14个几何描述量均有限、覆盖1.0，八角度RMSE约.163–.391rad只报告，非人体真值或R1关节跟踪门槛。
- 原生时钟审计发现首个mode2比实际开始消费参考早4tick/80ms。修改前预期native-clock-correction-expectation-20261101.json：只按原生逐帧SMPL/四元数身份求精确源起点，不做拟合，不重跑物理、不改实际轨迹；旧录像/指标/编码日志带哈希归档。1397行身份最大位置差5e-10m，原生时钟P95绝对漂移30微秒；按原生时钟重评物理仍passed、重渲染699帧全部实际状态有效，actual-state哈希不变。执行版本与离线渲染版本分别在source-provenance-audit.json保存并验证。决定keep。
- 最终完整demo passed：demo-native-aligned-02/comparison.mp4展示原片、2D覆盖/3D骨架和真实机器人，1600x480/699帧25fps；五个视频全量解码与首中尾画面检查通过，无剪辑/拟合偏移；填补和非三维真值标注保留。旧空机器人失败demo、旧80ms派生录像、可选psutil缺失的未启动渲染失败均保留。断开旧长终端发生在物理结束后，boot_id未变，不将其解释成新主机重启；后续离线任务用detached PID/boot_id/startticks及文件日志跟踪，已完成。
- 实测预算更新：七个非2D姿态阶段合计1438.08s，最后326帧冷却姿态597.73s（含导入、非完整无中断基准）；同长度外推+离线渲染约50–70分钟/条、10x30s约8.3–11.7h，仅规划，不含调试重启。最大框架保留BodyPose3,737,124,864B、姿态3,642,753,024B；全部串行阶段在8GB卡完成，不能外推实时并行。D占用19.22GiB/100GiB规划，C/D空闲19.25/272.05GiB，新增云费用0。源池新增3条舞蹈全片解码/20帧检查符合基本条件，无新增模型推理。
- 全部证据：runs/r2-preflight-youtube-QqvZAUEOrAQ-20261031-01/REPORT.md、results.json、各专项audit；Git摘要evidence/r2-preflight-20261101.json与r2-resource-estimate-20261101.json。这里只完成首条调试，5+5整批、GPU图形窗口仍awaiting_verification，相机needs_input，保留推理未使用；继续整批实现与调试，不结束活跃Goal。

## 2026-11-01 R2 默认检查点集成与冷导入精简

- 修改前预期 `runs/r2-setup-20261030-01/batch-integration-expectation-20261101.json`：不改模型/FP32/batch1/crop/增广/控制/门槛，默认入口使用已验证数值生产器；只有调度、持久化和不必要导入改变。保留旧冻结首片，不复用旧目录写新版本。
- 配置解析等价 `passed`：只使用官方load_mapping及相同相对路径解析，结果与首片resolved配置完全相同，冷加载1.6888s且无Torch/transformers导入。完整838帧静态相机使用相同已有视频/框/2D点重算，R_w2c、cam_angvel、diagnostics、K_fullimg逐字段完全相同；实际阶段141.81→30.87s，RSS约615.5MB，无模型GPU推理。首次验证harness因缺scripts路径在执行前失败，单独记录并修复验证入口；不是缓存/模型失败。
- 默认pose2d调度集成：主入口持有extraction.lock，worker仅调用同一官方生产器locked_run，有限ceil(frames/96)+1组，组内最多3x32帧，组间释放模型并休息≥30秒/低于55°C，开块<60°C，120秒热等待退出。生产器新增heldout冻结SHA/来源/源码/使用ledger检查；原数值predict路径未改，旧首片producer快照不改。CPU工具检查完成即停、热等待超时、有限组数、父锁单实例及合成heldout无ledger/改manifest拒绝均passed，没有实际保留数据或GPU模型。
- 真实新运行仍awaiting_verification：完整深蹲源0EpP3pYUYTk、258帧24fps→323帧30fps；提前按原片标注7个下蹲/站起事件，运行 `runs/r2-debug-squat-20261101-01/` detached PID115096、boot_id/startticks与日志保存，未重复提交。prepare10.2245s、detect144.5275s、features192.5158s已完成；姿态首96帧检查点通过，权重清理后约32秒/54°C再继续。随后物理/事件/全片demo尚待运行，不将检查点算作完整交付。
- 整批产物审计工具 `passed`（工具验证）：按运行快照解析阶段输出而非当前源码，核对原始输入SHA、全部8阶段输出SHA/源码快照、完整控制/真实状态身份和五段录像全解码、源时序及可用帧；视觉检查必须绑定comparison SHA，缺失则awaiting_verification。首片真实产物独立审计passed，空证据目录正确保持awaiting_verification。证据 `runs/r2-audit-tool-check-20261101-01/`。
- 精确帧映射辅助工具独立验证passed，尚未修改当前运行版本。按FFmpeg官方fps的精确有理数近邻舍入计算选帧，保留整数PTS/timebase；同滤镜图每个输出raw hash/size与所选输入帧核对。24fps原调试258→323帧和合成VFR22→60帧全部通过。MP4文件SHA不同，经全部323帧解码hash/时间网格核对完全一致；没有改源视频或将前一源帧误称实际选中帧，没有永久保存RGB。证据 `runs/r2-timeline-check-20261101-01/`，官方算法链接随工具保存。决定keep辅助工具，待当前提取结束再集成新版本。
- 来源分组初稿 `configs/r2-suite-draft.json`：5调试/5保留，保留覆盖舞蹈/躯干/下肢三类；三条舞蹈同创作者/场景相关性明确记录，不宣称独立场景泛化。Cupid原黑尾作为debug挑战保留；Whiplash元数据明确mirrored，记录true；其他镜像未知，不自动翻转。其余3条调试事件在任何3D/机器人结果前由源画面标注。尚未冻结、未用保留推理，云费用0，服务器未连接。

## 2026-11-01 第二片完整通过、观察器修复与整批准备

- 默认冷却姿态实现真实验证passed：深蹲全323帧完成，pose2d471.9569s、camera33.4426s、motion35.6985s、postprocess72.9309s，含独立D进程冷启动；全八阶段完成，原始258帧24fps源和全部中间结果保留。没有发生新boot变化；不能将此一轮外推为主机根因已解决。
- 初次物理failed：源参考消费192/539后，Python观察器读D盘正在写入的controller-input.csv返回ENODATA。原生控制未报跌倒，原始physical/、body-audit/、demo/全部保留。修改前预期live-csv-read-repair-expectation.json：只容忍明确瞬时读错误并记录计数，不伪造消费、不改变时限/控制/门槛。真实已停止CSV和故障注入检查passed：四种瞬时errno返回None、未知EIO传播、未结束的行999不遮盖完整行100；首次测试夹具错误按真实大文件stat定位小BytesIO而失败，修正夹具大小后重验，未启动物理。
- 同缓存新physical-attempt-02 passed：539/539源样本完整消费，无跌倒、最低根高0.459148m，7/7原片预标注事件通过；本次无瞬时读错误，策略/源参考SHA与原试次相同，新源码版本另存。demo-attempt-02/comparison.mp4270帧25fps，全部五个视频全解码、完整映射和首中尾人工画面检查passed；固定run-audit.json与REPORT.md/results.json保存。源码修复keep；不替换或抹去首次failed结论。
- 20项评估扩展预期与验证passed：setup/body-descriptor-extension-expectation-20261101.json；新增4项躯干角度/2项前后脚距符号，解析旋转/平移/尺度/环绕/退化输入测试通过；首片1397实际样本原14项全部人/机器人序列逐元素相同，旧六事件报告完全相同，新6项有限。新报告首片body-audit-extended-20261101/，旧报告不改；不是保留性能，不设新RMSE阈值。
- 精确选帧集成CPU检查passed：新目录r2-integrated-prepare-check-20261101-01验证源整数PTS/timebase与滤镜raw PTS逐帧一致，实际输出323帧与hash证明匹配；原先独立24fps/VFR检查和全部323个解码帧等价仍保留。新入口不保留RGB大数组、不裁源内容。
- 整批工具准备passed：freeze检查源SHA/来源分组/事件特征/调试审计/未使用ledger，冻结后记录源码/模型/原生二进制/GPU驱动/子模块diff；串行执行器跳过已有terminal审计并拒绝重复任务，失败和部分物理不自动覆盖；独立汇总在4/5完整且其余已完成时才通过，4成功+1未运行仍awaiting_verification、3/5失败、未冻结不能通过、错误来源使批次无效。合成边界验证不计保留使用。所有5条保留事件只按原片提前标注，仍未运行保留模型；freeze-readiness仅剩三条未完成调试。
- 当前debug2/5passed，heldout0/5used，R2及Goal未完成。后续串行继续另三条调试再冻结保留，云费用0，服务器未连接。Git小型证据evidence/r2-debug-progress-20261101.json，所有原始产物仍D。

## 2026-11-01 剩余调试串行执行与提取覆盖诊断

- 整批续跑已启动：`runs/r2-debug-orchestration-20261101-01/`，PID122594、boot_id/startticks记录在task.json；来源/配置/源码840bb87已推送GitHub。跳过两个既有passed审计，臂环绕完整原片424帧25fps→509帧30fps，精确整数PTS/raw哈希prepare12.3637s和CPU检测277.8107s通过，features进行中；下一条踏步，再Cupid。只运行debug，保留仍未使用。
- 修改前预期（诊断本身不改模型）：用两片已保存2D/框缓存描述覆盖率、缺口、置信度，仅CPU、不创建新质量门槛。首片primary观测398/838、补框440、末419帧从13.97s起沿用旧框；深蹲323/323全部primary观测。SMPL24映射关键点置信度>0.25比例分别95.62%及100%，不是校准准确率或3D真值。原始检测与模型输出文件SHA不变；诊断文件在两片extraction-diagnostics-20261101.json。
- 进一步纯CPU重放首片stored raw boxes/scores→官方ByteTracker，主轨迹observed mask逐位完全一致passed。raw检测800/838帧有框；ID0活动398帧[19,418]，ID3活动401帧[405,818]；官方最大累计面积规则只选ID0，后续因此持有旧框。不是后半段全无原始检测，也不能单凭补框推断姿态错；原6个事件及实际物理通过结论限于既有门槛。证据tracking-fragment-audit-20261101.json、extraction-diagnostics-annotated-20261101.json。记录为当前官方跟踪覆盖局限，不在正在运行的固定版本中调整阈值/改轨迹关联。
- 决定keep原运行及诊断，继续余下调试，完成后按原5+5/至少4保留门槛验收。云费用0，未连接服务器或真机，没有训练/驱动修改。

## 2026-11-01 冷却目标低于实测空闲温度，转为逐帧间歇验证

- 原臂环绕pose调用退出failed（resource scheduling）：447.00s、0/509帧，框架权重释放后分配9,756,672B，系统空闲约6.4GiB，123s观察末温度59°C而要求<55°C；原生两帧数值等价已通过。不能解释成8GB不足或提取数学错误；有限观察退出与所有原证据保留。
- 代理核对串行父PID122594的boot/startticks/pgid，确认无g1控制器运行后SIGTERM仅自己的进程组，保存agent-stop-for-cooling-repair-20261101.json。踏步当时CPU检测随队列主动中断，prepare等完整缓存保留；不是主机重启，不将未知进程退出归因硬件。
- 新辅助调度修改/运行前预期：单片paced-recovery-expectation-20261101.json。原数值生产器、FP32/batch1/翻转/crop/数据时间轴/32帧缓存不变；每帧后CUDA同步+0.5s真实idle，避免长连续GPU突发；起算温度≤65°C，75°C触发降温到65°C、80°C采样立即停止并释放模型，资源等待有限。以已独立保存native预测做严格逐元素一致对照，然后最多32新帧试算。没有改驱动/风扇/功耗/OS设置或动作/物理门槛。
- CPU调度检查passed：模型模拟值完全相同、两帧实空闲1s、滞回等待、300s超时前无kernel、80°C单帧后停止，setup/paced-scheduler-check-20261101.json；不作为GPU结果。真实probe PID126389/startticks1017227已在同缓存启动，当前仍模型冷加载；最终GPU等价、温度和源帧审计awaiting_verification，源片/原失败/所有源码快照保留，保留数据未使用、云费用0。

## 2026-11-01 用户改为吞吐优先，再关机迁移服务器

- 用户明确新指示：“优化温度上限，快速推进任务，关机就换服务器，不要过度防止中断”。此前自行设定的低温目标和逐帧休眠已退出当前路线，原试算代码/原始日志/预测证明保留；不更改动作/物理验收或源视频。启动/Goal提示和执行策略已同步，活跃Goal仍为R2，不冒称完成。
- 两轮逐帧间歇硬件结果：原生对照2帧逐元素一致passed；首轮18次调用（含2证明）触发81°C，第二轮5次调用触发82°C，均未形成32源帧checkpoint，所以温度目标failed/完整姿态awaiting_verification。第二轮逐帧记录显示64→82°C瞬时变化，不能把人为80°C观察线误当既定项目验收。数据/源码快照均在臂环绕pose2d-checkpoints和各probe日志，未用保留视频、未发生新主机重启。
- 新执行策略configs/r2-execution-policy.json：原生FP32/batch1/flip/crop/完整时间戳不变，取消软件温度等待和额外逐帧休息，保留真实温度/显存记录及32帧耐中断缓存，设备自身温控不变。起算仍要求显存余量，不改驱动/风扇/功耗/时钟；本次boot_id作为本机运行基线，若改变停止本机试错转服务器。没有启动服务器或计费云。
- 同一臂环绕缓存原速恢复已启动PID127785/startticks1142422；辅助入口run-r2-throughput-recovery.py只替换metadata持久化，原数值生产器SHA仍ef1c785c6b3d9cd49f05f32c95cc398b3d87997ae9acfb290eef380210fc4cd2，真实资源值不伪造。后续串行父队列PID128105/startticks1159726先等待已存在任务而不重提，然后继续其余提取/物理/三路demo和另两条调试；仅原温度等待失败审计会带SHA归档后按用户新策略恢复，不自动替换真实物理/模型失败。原两片passed和全部失败/主动中断证据保留。

- 新策略第一项真实结果passed（完整2D姿态）：臂环绕509/509帧通过，原native两帧proof和各块身份保持一致；416帧时实际温度72°C/系统GPU4759MiB，未新增重启。只是完整观察量缓存，不提前计完整视频/物理通过。协调器的resource-only匹配最初查外层error而详情在worker log，因而跳过已恢复源；保存了活跃协调器实际源码，修正后以单独串行follow-up等待主队列结束再完成臂环绕3D/物理/demo，正在执行的踏步/Cupid不中断。两片已通过、原冷却失败、两轮间歇失败和所有原始缓存均保留。


## 2026-11-01 原速队列、踏步失败与完整结果包

- 预期：保持原生FP32/batch1/flip、完整源时间轴、50Hz参考和所有物理/事件门槛；仅移除人为温度等待。先完成剩余调试，保留所有失败，再冻结保留集。报告/API修复与固定起始衔接诊断各自在setup/diagnostic expectation.json中先记录预期。
- 运行结果：臂环绕509/509姿态原速检查点 `passed`；踏步八阶段提取/转换 `passed`，341原帧、344提取帧、574参考。真实物理 `failed`，22/574源样本后跌倒，源覆盖0.412781s、最低根高0.192953m，真实状态SHA ab3ef4ebc77429a5784b06a921b09967abceb6443036e8b883c3ec2530df38d6。弹力带在源期间关闭，无状态覆写；没有主机重启、OOM或观察CSV中断证据。6事件因覆盖不完整均不通过，不能归为完整动作提取失败。原初审failed未改。
- 媒体/交付：踏步完整287帧对照含原片、2D覆盖、3D骨架，实际录像只有11帧，后段明确标记停止。5个MP4完整解码passed，人工核验0/10/143/274帧passed；物理/整片仍failed。新增REPORT.md与run-audit-media-review-20261101.json，原run-audit.json及全部实际状态未覆盖。审计修复分别检查完整对照和真实短录像的长度，伪造尾部可用标记或物理passed但实际缺帧仍拒绝；旧深蹲完整270帧/7事件复核passed。
- 实现：新增单视频原速入口，缓存结果只读、活跃队列防重复、保留源必须走冻结入口；缺预标注事件不能算通过。冻结状态改为明确的at_freeze快照，保留调试审计SHA；真实运行检查原生binary SHA及两个固定上游revision/diff。局部CLI、正/负身份、媒体回归passed，只是工具验证，无新保留模型调用。
- 调试分析：源开始比策略启动晚1.08185s；正式源开始前机器人高度已从0.9645降至0.6036m并倾斜，随后跌倒。踏步首参考右膝屈曲1.82777rad，固定首姿态50帧预热可能造成站立→高单腿的突变，尚未确认根因。独立诊断准备固定100帧/2秒骨方向SLERP+smoothstep前缀，保留首四元数/上半身与腿骨长，全部574原始运动样本逐值不变，最大骨长误差5.96e-8m；CPU几何边界检查passed，真实执行awaiting_verification。单次诊断PID136971在Cupid+臂环绕队列结束后运行，绝不覆盖原失败或纳入canonical通过计数。
- 活跃任务：Cupid检测1470.001s passed，features继续；主队列PID128105、臂后续PID129032均在同一允许boot上。调试现2passed/1failed/2待验收，保留0/5；运行预算不变，云费用0。本机再次关机就按用户要求停止本机重试，待接入服务器迁移。
- 证据：踏步runs/r2-debug-6uqztDO_7kQ-20261101-01/{REPORT.md,startup-fall-diagnosis-20261101.json,run-audit-media-review-20261101.json,visual-failure-review-20261101.jpg}；setup/{single-video-entry-check,frozen-runtime-guard-check,report-media-regression}-20261101.json；runs/r2-startup-transition-diagnostic-20261101-01/{expectation,geometry-check,preparation,task}.json。keep实现/证据，诊断真实结果未出前不修改主物理/转换源码；5调试完成后再冻结保留。


## 2026-11-01 最长调试片特征与CPU检测瓶颈

- 上一Goal轮为实质进展：提交并推送095b315，一键入口、冻结身份、失败媒体审计和调试起始衔接源码已保存；本轮直接检查同一boot/startticks的活跃进程，没有重复任务。
- 实测 `passed`（仅单阶段）：Cupid完整1771帧/59.033s视频，CPU检测1470.001s，GPU特征529.009s，系统总显存峰值4931MiB、进程树峰值4,370,276,352B；完整3D/物理/demo尚awaiting_verification。原速姿态PID138962已接续，D盘冷加载约3分钟后显存与RSS上升，实际进程持续活动，未因观察超时重启；软件温度门槛关闭，原生FP32/batch1和32帧检查点不变。
- 调度修复预期先记录：默认ORT CPU检测持续使用近32线程，长片检测成为瓶颈。新benchmark-r2-detection.py在前序所有队列与启动衔接诊断结束后，以固定8/1线程对完整344帧踏步调试片做一次同模型/解码/阈值/NMS/官方跟踪与裁剪对照。全部raw_boxes/raw_scores、track/frame IDs、observed/valid_span、主框/平滑裁剪框、其他人物框和填充标签逐值相同才通过；任意差异failed。候选另存D目录，原缓存哈希前后核对，尚未修改现行提取源码或采用该线程设置。
- 当前只是源码/串行调度准备：PID138951/startticks1502463/boot fa0233fb-701c-42d8-81da-0d007d2efe7d等待PID136971，等价/性能awaiting_verification，无新增GPU推理或保留使用。期望/源码快照/任务日志在runs/r2-detection-throughput-check-20261101-01/。若速度有提升，报告两轮导入/缓存热状态不同，不能把worker总耗时当作纯模型速度对比。
- 冻结只读预检正确返回awaiting_verification，当前缺Cupid最终调试审计；臂环绕资源失败仍由既定后续队列处理，不能把这次预检当作可以提前进入保留集。云费用0。


## 2026-11-01 全调试提取覆盖诊断及长片原速姿态

- 预期：先在setup/extraction-diagnostics-expectation-20261101.json记录，只读已完成缓存并核验SHA，重现首片既有数字；描述检测/轨迹/原始热图置信度，不修改输入、模型、裁剪或验收规则。
- 缓存诊断计算passed：新diagnose-r2-extraction.py读取全部5条调试检测缓存，首片原始800/838、主轨迹398/838、映射24点置信度>0.25比例0.9561953062848051与旧诊断逐值一致；深蹲主轨迹323/323、臂环绕508/509（填1）、踏步344/344（无填框）、Cupid1723/1771（末48帧填框）。Cupid当次2D尚未完成，明确标pose_confidence_status awaiting_verification；不拿局部缓存补全统计。置信度是模型raw heatmap maximum，非校准概率或人体真值。
- 工具实现/验证：未来串行入口在完整提取后生成extraction-diagnostics.json，结果报告链接最新诊断，helper入冻结CODE。五份实测摘要在各run/extraction-diagnostics-20261101-02.json，setup/extraction-diagnostics-check-20261101.json记录首片等价和五缓存覆盖；这是CPU只读分析，没有额外GPU模型或保留推理。踏步REPORT补链接，actual-state SHA ab3ef4ebc77429a5784b06a921b09967abceb6443036e8b883c3ec2530df38d6及failed原结论均未变。
- 最长片真实运行passed（仅2D）：Cupid1771/1771原生姿态、56个分块全部完成，wrapper690.229s、完整子进程invocation767.738s（两者包含的启动区间不同，不能当纯模型速度）。原生FP32/batch1/flip及32帧持久化未变，无冷却/逐帧休眠、无新增重启；框架峰值allocated3,540,864,000B/reserved3,642,753,024B。随后camera45.292s、motion47.016s、postprocess87.883s均passed，convert尚在运行。完整实际仿真/事件/demo仍awaiting_verification，调试2passed/1failed/2待验收、保留0/5不变，云费用0。


## 2026-11-01 原速预算更新与长片完整消费

- Cupid全部8阶段提取/转换passed；原始1771帧、归一化1771帧、2952个50Hz源参考。原生记录2952/2952源样本，参考joints最大身份差4.99994e-10m，源时钟P95绝对偏差49微秒，无拟合平移。run-events源完成true/failure null，一次瞬时ENODATA由已验证CSV观察修复容忍，未停止实际控制。实际录像仍在渲染、身体事件及整片审计awaiting_verification，不能先计通过。
- 资源实测/预算复核passed（只测量）：踏步11.467s与Cupid59.033s的8阶段worker合计19.494/50.908min，完整提取协调合计20.967/54.760min；插值30s提取34.134min，加物理/身体/全媒体及导入波动，更新单30s全链路40–50min、10条平均30s约6.7–8.3h、剩余5条既定长度保留约2.5–4h。两片缓存热状态/温度/启动开销不同，属于规划外推，不是纯模型基准或通过承诺，也不作为超时重提依据。
- 旧冷却估算保留并注明已被原速方案替代；尚未执行/采用的CPU线程加速没有计入。100GiB规划和磁盘保护线不变，新增云费用0，无保留推理。原始逐阶段profile与resource-throughput-review-20261101.json在Cupid运行目录，可同步摘要evidence/r2-resource-estimate-20261101.json。


## 2026-11-01 Cupid物理与事件通过、离线画面提速对照

- Cupid正式物理passed：2952/2952源参考完整消费，实际源覆盖59.034645s/11808样本，无跌倒/过量倾斜/非足接触，最低根高0.5996363824m，源期间弹力带关闭，重力/接触/自由根部/扭矩控制启用，无实际状态覆写。实际状态SHA47f80f12d23f0a7dca741fb399c6088ec13fe7a83d8fb5632e141c3838f7b44c；身体评估passed，预标注5事件方向/顺序5/5通过，robot-minus-extracted时间差[0.22,0.46,0.12,-0.06,0.04]s，只报告时间差、不拟合平移。完整对照和独立审计仍在生成，调试canonical计数尚未增加。
- 全1771帧缓存置信度补齐：extraction-diagnostics-20261101-03.json明确原始/主轨迹1723帧，末48帧/1.6秒沿用框；SMPL24置信度>0.25比例0.9728966685，但只是非校准描述、不是准确率。早前02报告的2D待验证状态保留。无额外模型推理。
- 实际状态录像CPU软件渲染较慢，期望先写runs/r2-render-throughput-check-20261101-01/expectation.json；独立复演相同0/29.5/59秒三状态，对照默认光照与关闭阴影/反射（无物理步进或在线控制）。三个分割几何图逐元素相同，状态文件SHA不变，图像首/中/尾人工核验passed。热身后的默认RGB单帧[0.4821,0.4939,0.4477]s，对照[0.2383,0.2440,0.2006]s，中位比2.023；背景原CPU渲染仍在，不能外推为纯独占硬件或全视频已通过。source.py/probe.log/comparison.png/comparison-reviewed.json留原始证据，现行渲染设置未改。EGL仍走软件路径，GPU图形/窗口没有因此passed。
- 期间一次不可读/proc编码器I/O节点被误解为退出，随即以真实ps存活和文件持续增长纠正；没有终止或重跑任何任务。最终原渲染正常结束后才读取正式physics/body指标。keep该候选，待既有所有队列与同控制脚本的起始衔接诊断结束后再统一启用/测全视频，不破坏当前缓存身份或受控对照。


## 2026-11-01 第三片Cupid完整调试正式通过

- 完整视频、提取、转换、实际物理、身体/事件与最终媒体审计全部passed：原始/归一化1771帧/59.033s，2952/2952源参考，真实状态未覆写，最低根高0.599636m，5/5预标注事件方向/顺序通过，无拟合时间偏移。native source clock P95abs49微秒，actual-state SHA47f80f12d23f0a7dca741fb399c6088ec13fe7a83d8fb5632e141c3838f7b44c。
- 三路comparison1476帧/25fps/59.04s，source/extraction/robot/comparison及实际状态录像共5个MP4全帧解码passed，所有实际机器人帧可用。人工核验25/737/1463帧：原片、2D、3D与真实机器人对齐清晰，原片最后48帧黑尾完整保留，填框标记可见；visual-audit绑定最终comparison SHA58a851a72563c594cf561627c0e331033c2a2859e0bace944931d41c49a1a631。
- 证据runs/r2-debug-2e_7XBmpw14-20261101-01/{REPORT.md,run-audit.json,visual-audit.json,demo/comparison.mp4}。初审awaiting文件保留，最终审计另存canonical；没有改写原实际轨迹或源参考。当前调试3passed/1failed/1待验收，保留0/5；整批仍awaiting_verification。代码/小摘要已持续提交，不上传大模型、受限资产或凭据，云费用0。
- 主队列PID128105已退出，旧调度failed包含踏步实际失败及已被单独恢复接管的旧臂资源失败，不重启。后续PID129032正在完成臂环绕转换/物理/demo，camera/motion/postprocess缓存已完整；随后自动运行同原控制脚本的踏步起始衔接诊断PID136971，再执行完整CPU检测线程对照PID138951。暂不修改这几个活跃对照依赖的原物理/提取/渲染源码。


## 2026-11-01 五片旧调试完成、统一初始化生产修复与回归启动

- 原五片最终3passed/2failed：臂环绕849/849源参考完整、无跌倒、最低根高0.7811798285m，但最后right-arm-down的机器人外展比例min0.3128013638高于原阈值0.2；提取参考min0.1225301288，3/4事件，整片failed。425帧全对照/5媒体解码及首中尾视觉passed，actual-state SHAa8e7bf79fc70600066194464838b6dccb796feeeb1f3fb503efc6c20121e52eb，原canonicalfailed和补充run-audit-visual-20261101.json均保留。没有通过更改阈值使之passed。
- 起始衔接消融物理passed：同硬件/二进制/策略/模拟器，用固定100帧/2秒中立腿→首姿态前缀，完整原574源参考执行，无跌倒，最低根高0.6969662007m，实际SHAa5eb9ef308756f624b67e43b4ed16ff004b10b30e0b752f4e9d71cbf05a43f1f。原初始50帧静置仍保留；没有改变任何原源样本/间隔/事件/物理门槛或实际状态。它只是debug消融，不替代新生产全链路。
- 生产实现：r2_initialization.py定义50帧中立静置+100帧smoothstep骨方向过渡，全部原视频参考随后原值发送，future仍51。run-r2-physical记录reference_initialization及helperSHA，evaluator按明确150前缀核对所有原生样本后，以第150帧作为视频0，不搜索/拟合时间平移；缺该metadata的旧50帧试次保留原逻辑。全量March包与已成功诊断reference-wire.bin逐字节相同（SHA7ed200e4df8e8da58c38fe19f964d893c5780d88b3d27db82a0abdb11bae73ed），五source全部字段在150后相同，三条旧clock报告逐字典相同；真实诊断source ticks与固定slice逐值相同。CPU协议/旧兼容/源保留checks passed，仍需生产五片实跑。
- source-only重新核查原6个踏步事件0/6，提取本身在预标注侧别/窗口中未达阈值，故物理变稳定不等于该片方向正确。保留原标签/阈值/窗口，记录侧向歧义尚未解决，不按模型结果互换左右或改窗口。
- 提速验证：CPU ORT8/1完整344帧、1381叶数组/轨迹/裁剪等0差，原缓存不变；候选worker251.203s对原356.671s，纯decode/detect/track212.931s，导入/缓存热状态不同，不能当纯模型速度比。生产r2_detection工厂另以0/172/343帧框/分数逐值相同、线程8/1及原工厂恢复验证passed；已应用新worker配置，FP32/阈值/NMS/权重不变。
- 对照读帧优化：生产read_video_frame按相同索引顺序read/grab，避免重复GOPseek。1476个原片25fps选定帧、1476实际帧、11个失败实际帧及EOF逐一BGR SHA相同，原MP4不变。仅机器人读帧39.937→1.715s约23.29倍（解码组件，不是pipeline），生产forward函数全选帧proof也passed。离线实际RGB关闭阴影/反射，已用三个同qpos/相机分割图相同+人工视觉验证；只改画面，无物理步进/状态写回。新actual-render-mapping记录该设置，分辨率/fps/时钟不改。
- 缓存复演实现：r2_cache抽取原审计的8阶段/原片/源快照SHA检查，五旧摘要与旧审计逐项相同。run-r2-cached-suite为全部5debug建独立新run和来源指纹，明确不计新ML推理；旧源缓存和实际状态不覆盖。新run_video只允许debug显式复用，不允许替代heldout首次推理；最终summary保留previous_attempts。准备/协议/pixels/CPU工厂checks后启动PID149562/startticks1906410，同一boot；每源核对源缓存、代码、GPU/二进制/策略/评估一致。
- configs/r2-suite-draft.json仅更新debug试次位置并保留previous_attempts，5个heldout、源SHA/事件与划分完全不变，保留尚0/5使用；首新Qq控制1397/1397、无跌倒、6/6事件passed，完整demo生成中。当前为五片统一回归awaiting_verification，不把旧3passed或消融passed算成R2结项。云费用0，100GiB计划不变。
- 证据：runs/r2-initialization-regression-20261101-01/{expectation,protocol-clock-check,cache-verifier-check,task,runtime-identity,code-identity}.json与原/派生manifest；r2-detection-throughput-check-20261101-01/{comparison,production-factory-check}.json；r2-demo-read-check-20261101-01/{comparison,forward-comparison}.json；源码前后快照与所有原试次均保留。


## 2026-11-01 统一初始化五片回归完成、冻结原保留集并启动

- 预期和身份：生产五片回归沿用各自完整原提取缓存，SHA核对后重新实际执行控制/事件/完整demo；50+100帧初始化后原6311源参考全部保持。protocol-clock-check及cache-verifier-check通过，所有源保持同一代码、硬件、权重、二进制和原事件规则。
- 完成结果：5/5物理稳定，Qq1397源/6事件、深蹲539源/7事件、Cupid2952源/5事件整片passed；臂环绕849源、3/4事件failed，踏步574源/0/6事件failed（新最低根高0.724520m、无跌倒）。所有5片均有完整源/2D/3D/实际机器人对照，5MP4全解码和首中尾视觉通过。不能把物理改善算成事件通过，旧跌倒/中断/成功全部保留。证据runs/r2-initialization-regression-20261101-01/reviewed-results.json及五条新run审计。
- 冻结检查passed：configs/r2-suite-frozen-20261101.json，SHA c3403dc4581ed61880e66f3c4cbbaa84961c1455621c0e5f170c10c0006378d1，42代码/配置/事件文件、15资产身份以及原生二进制/GPU驱动/上游版本与补丁。固定原5debug+5heldout及至少4/5门槛，冻结前台账无任何保留使用。提交42463b0保存实现与清单。
- 2026-11-01 08:17 Asia/Shanghai启动原5条保留队列runs/r2-heldout-orchestration-20261101-01，PID157620/startticks2109756/boot fa0233fb-701c-42d8-81da-0d007d2efe7d；首片ROZy7jawHf4于unix1793492321.5185695登记使用（source SHA a3f05efb4b5abb965708a865f87ce8974cac54df2e57c7f3bed6a0d30398e335），当前1/5使用、0/5完成。检测已完成、特征推理进行中，未新增本机重启，不因导入/观察等待重提任务。原速FP32/batch1/flip、32帧检查点，无人工冷却等待；新增云费用0。
- 冻结后的false标志只描述冻结时刻；当前使用以D盘runs/heldout-use-ledger.jsonl的distinct input_sha256计数。保留开始后不更改冻结实现/标签/阈值，不按结果重选样本。整批仍awaiting_verification。


## 2026-11-01 首条冻结保留完整通过

- ROZy7jawHf4全新8阶段提取/转换passed，完整421源帧、421归一化帧、702/702原生50Hz源参考；实际物理无跌倒，最低根高0.7759068039m，源窗口全覆盖、弹力带关闭、自由根部/重力/接触/控制启用，实际状态没有覆写。预标注8个躯干左右交替事件方向/顺序8/8通过，不拟合时间平移、不改阈值。
- 完整对照351帧/25fps，所有实际机器人帧可用；5媒体全帧解码passed。人工查看demo25/175/338帧，原片、2D、估计3D和真实机器人画面清晰/时间戳一致，visual-audit绑定最终comparison SHA9d2cd1b0b7561268b5b74e94cd85c9eada3abf8078bc5fa1ad22ad4cafea1852。canonical run-audit.json正式passed，并绑定冻结清单SHA c3403dc4581ed61880e66f3c4cbbaa84961c1455621c0e5f170c10c0006378d1。
- 原速姿态421/421、14个检查点全部持久化，wrapper284.344s；包含启动的native invocation321.929s，两者范围不同；检测273.817s、特征237.091s、相机38.160s、运动41.71s、后处理84.27s、转换83.618s。GPU观测峰值约4.9GiB；样本温度71–76°C，无人为冷却/逐帧休眠，无新增本机重启。单短片含固定导入开销，不据此宣称所有30秒片相同速度。
- 证据runs/r2-heldout-ROZy7jawHf4-20261101-01/REPORT.md、run-audit.json、visual-audit.json、demo/comparison.mp4；系统已自动开始第二条U7Nrwyu6Uqo。当前2/5保留已用、1/5完成并通过；剩余4条必须全部报告，R2整批仍awaiting_verification，新增云费用0。


## 2026-11-01 第二条冻结保留后撤弓步完整通过

- U7Nrwyu6Uqo原224帧/7.4667s，全部8阶段提取/转换passed，374/374原50Hz源参考完整实际执行，无跌倒、最低根高0.4847076961m。6/6预标注后撤/站起事件方向与顺序passed，实际与提取峰值时间差保留（包含0.7s差异），未拟合偏移或改变阈值。身体误差仅描述相对提取参考，非人体三维真值。
- 完整187帧/25fps对照及5MP4全帧解码passed；人工查看25/93/174帧，原片、2D、3D与真实机器人均清晰、时间戳一致；机器人仍有可见相位/幅度差，未在视频中掩盖。visual-audit绑定comparison SHA0d97b3f159b9327d1b2f373167cabd0e919d66159c538d96f09e69561fa9c971；canonical run-audit.json passed并绑定原冻结清单SHA。
- 原速姿态224/224与7检查点全部完成；检测172.13s、特征207.68s、姿态wrapper235.93s、相机37.79s、运动41.72s、后处理84.62s、转换83.63s，范围见各原始profile。没有人为冷却或本机重启；云费用0。证据runs/r2-heldout-U7Nrwyu6Uqo-20261101-01/{REPORT.md,run-audit.json,visual-audit.json,demo/comparison.mp4}。
- 当前3/5保留已用、2/5完成并passed；第三片gRexOgq8h-8全新推理已自动启动，原5来源/事件/≥4/5门槛不变。后三条舞蹈同创作者场景，属于相关来源的工程检查，不据此声称独立广泛泛化；全部5片仍须出结果。整批awaiting_verification。


## 2026-11-01 第三条冻结保留K-pop完整通过

- gRexOgq8h-8完整31.133s/934源帧，8阶段提取/转换passed；1557/1557源参考实际完整执行，无跌倒，最低根高0.6506392562m。原生时钟P95abs35.2微秒、全源身份核对通过，无拟合时间平移。6/6预标注下蹲/举臂等舞蹈事件方向和顺序passed；身体误差仅相对提取参考，单目结果不是人体真值。
- 对照779帧/25fps，所有实际机器人帧可用，5MP4完整解码passed。人工查看25/389/766帧：完整原片、2D覆盖、估计3D骨架与真实机器人均清晰，脚部/抬手可见，源时钟一致；实际仍有幅度/相位差，未掩盖或拟合移位。visual-audit绑定comparison SHA9dbe15c44f885c207dbc9dde61644e42e76bdc2a2eebd3d668b45578a2b363af，canonical run-audit.json正式passed并绑定原冻结清单SHA。
- 特征阶段曾实测GPU80°C/90%利用率继续计算；没有旧软件温度门槛/逐帧休息，没有新增重启。原生FP32/batch1/flip与32帧检查点不变。resource-review.json从原profile和checkpoint直接提取耗时/显存/检查点温度范围；温度范围只针对完成块的采样，不冒称全程峰值。新增云费用0。
- 证据runs/r2-heldout-gRexOgq8h-8-20261101-01/{REPORT.md,run-audit.json,visual-audit.json,demo/comparison.mp4,resource-review.json}；当前4/5保留已用、3/5完成并passed，第四条dIfUVvoVXRM已经开始。后三舞蹈来源相关，保留工程门槛及限制说明；须全部5片出结果，当前整批仍awaiting_verification。


## 2026-11-01 第四条冻结保留K-pop完整通过

- dIfUVvoVXRM完整35.733s/1072原帧、8阶段提取与转换passed；1787/1787源参考真实完整执行，物理passed、无跌倒，最低根高0.6599265038m。5/5预标注举手/头侧手位/屈膝事件方向及顺序passed，无拟合时间平移，不改变原上传镜像约定。
- 完整894帧/25fps对照，所有实际机器人帧可用，5MP4全解码passed；人工查看25/446/881帧，原片、2D、3D与真实机器人可见且源时钟一致，幅度/相位/画面朝向差异保留，视觉核验不宣称编舞完全一致或人体真值准确。comparison SHA59b06a3c9bf95f658b3bdf6a2b1030a5d08dcf4c5112ef7a74aa3f79d517ea0d，canonical run-audit.json正式passed并绑定原冻结清单。
- GPU计算时曾观察到约79–80°C/93–98%利用率继续运行；原生FP32/batch1/flip、32帧检查点不变，无人工冷却、软件温度中断或新增本机重启。完整证据runs/r2-heldout-dIfUVvoVXRM-20261101-01/{REPORT.md,run-audit.json,visual-audit.json,demo/comparison.mp4}，云费用0。
- 第五条GP4YqDYMmcI已自动开始，全5条保留现均标记使用；当前4/5完成并passed。虽然已达至少4条通过的数量，原验收要求全部五片都有结果，故R2整批仍awaiting_verification，继续最后一片后才结项。


## 2026-11-01 R2完整5+5工程验收通过及收尾

- 预期在r2-heldout-orchestration-20261101-01/final-review-expectation.json先记录；原5调试+5保留和≥4/5门槛未改。冻结汇总器最终passed：debug5终态（3passed/2failed）、heldout5终态（4passed/1failed），全部来源/历史失败进入报告，未因已达4条提前结项。
- 最后GP4YqDYMmcI完整818帧→1364/1364参考真实执行，物理passed、无跌倒、最低根高0.725450579m；wide-crouch预标注left-knee阈值0.7rad，参考max0.481388、机器人0.414427，5/6事件，整片failed。682帧完整对照、5媒体全解码/首中尾及22.92秒失败时点视觉核验passed。单目侧别/深度/标注根因尚未独立确认，不把参考数值当人体真值；原canonical failed初审与run-audit-visual-20261101.json补审均保留，未改标注/阈值/推理或重跑。
- 最终产物审计passed：当前10个完整结果包、50个MP4全解码证据与当前文件SHA重新绑定、全源/实际帧完整，10/10当前物理稳定，共12095源参考（保留5784）；旧实际跌倒/中断和成功全部保留。原调度退出failed代表含1个失败源；原冻结整批规则≥4/5则passed，原日志不改写。
- 冻结身份passed：42代码/配置/事件、15模型资产、5原调试审计哈希、原生二进制、GPU/驱动及上游版本/补丁全部匹配。无保留来源互换或据结果调参，所有5条已标记使用；后续不能再称未见。当前无模型/控制进程。
- 原速策略保持FP32/batch1/flip、32帧持久化，无软件温度等待/逐帧休息/强制冷却；GPU约80°C时继续计算，本轮未新增重启。五条保留至初审/媒体就绪约158分钟，最终视觉/报告另记；D实占19.884GiB、C余19.09GiB、D余271.38GiB，新增云费用0。
- 最终结果runs/r2-suite-acceptance-20261101-01/{REPORT.md,suite-summary.json,artifact-review.json,source-results.csv,completion-review.json}；原始storage-cost-review/frozen-identity-review在队列目录。报告生成的一处引号错误已修正，只有报告构建受影响；运行/数值证据未改。小型预览原样复制到evidence/r2-kpop-demo-preview-20261101.jpg并附来源，模型/原片/大视频不入Git。可同步摘要evidence/r2-acceptance-20261101.json。
- 分项：源码/环境、无界面实际控制、真实状态离线回放passed；GPU图形窗口awaiting_verification，现场相机needs_input。这是R2的工程验收，不宣称人体3D真值、编舞完全一致、R3实时或R4已完成；整个项目未完成。


## 2026-11-01 英文GitHub项目主页与后续网页准备

- 先记录可检验预期：`runs/project-homepage-20261101/expectation.json`；已读PLAN和用户引用两条聊天，采用最新R1 10/10、R2 heldout4/5而非延续聊天中的旧R2状态。用户明确改为完善已有私有仓库，不新建/公开仓库。
- 实现：HumanMimic英文README、insights、研究设计、架构、完整结果和复跑说明；保留原README为明确标注历史的operations.zh-CN.md。原创SVG首页与pipeline区分已实现闭环和未实现R4；展示帧来自已有完整MP4的15.56s，记录来源和SHA，没有新仿真或更改实验数据。
- 网页准备：参考用户指定PI/Anthropic的克制编辑式排版，完成暖纸/衬线/细线视觉、全10源结果表和筛选；仅本地HTML/CSS/JS，无部署、外部字体或模型调用。设计和后续发布说明在docs/website.md。
- 本地检查passed：90个新文档路径初检、章节锚点、SVG/JS解析；Chrome四宽度1440/768/390/320无页面横向溢出，图片完整、筛选数量正确、无JS仍显示全10行、键盘跳转入口与缩小动态效果可用。首轮图片检查在lazy-load完成前断言失败，等待decode后重验通过，不修改或隐藏缺失资源。
- 内容审计passed：所有十条源/事件/状态与原接受JSON一致，十段完整comparison SHA及全部必要本地产物路径重新检查；scripts/configs/既有evidence/子模块指针未变，既有人为DDS补丁保留。源码解析和展示验证仅指本轮资料；未新增动画/无界面控制/现场相机验收，R3仍needs_input、R4未实现。
- GitHub Markdown渲染API操作被自动审批拒绝（额外非公开内容传输），未绕过；改用本地marked和Chrome渲染，明确其不是GitHub真实CSS。检查/截图在runs/project-homepage-20261101/，小型摘要evidence/presentation-20261101.json。当前本地准备passed、GitHub默认分支发布awaiting_verification，云费用0。

- GitHub交付核验passed：内容提交`ff1c621ab4ea805b574dd0d81e38b2603bcce886`已快进默认main（原710f10e），包含已验收R2历史及本轮展示；原codex/r2-video-pipeline保留。连接器回读默认README及全体docs/website共18个blob与本地逐一一致，visibility仍private；About英文简介和5个主题已更新。独立网站未部署；本轮无新增实验/云费用。


## 2026-11-01 Linux服务器迁移与R4交接文档

- 用户要求介绍R4并整理可交接的上下文，已先读PLAN现状/验收与已有英文研究设计，不另起R4路线；可检验预期、源HEAD/分支、旧补丁与受保护文件SHA在runs/linux-handoff-20261101-01/。源HEAD9808b03，交接分支codex/linux-handoff。
- 文档准备passed：根HANDOFF.md覆盖用户偏好/授权、R1/R2结果与全部失败、已使用测试台账、两套conda/SDK和非Git资产、WSL绝对路径/owner/boot/硬件冻结适配、V100兼容风险、迁移回归与原R4里程碑/10开发+至少20冻结测试/四方法/至少3个改进布局/完整录像。README、准备指南、研究文档、PLAN及启动提示加入入口，保持现有英文展示。
- 只读观察：当前无项目模型/控制任务，无活跃Goal；WSL boot da152f79-87d4-4995-876b-7bb6b59456c8不同于R2验收boot，不能据此确认Windows重启原因，按旧策略不恢复本机推理。已安装Torch编译元数据R1不含sm70、R2含sm70；没有启动CUDA内核/模型/物理。官方TensorRT文档核实Volta支持止于10.4，现用10.13.3不能直接用V100；新server版本需独立验证，未改现有环境/驱动。
- 本地文档/一致性检查passed：74个本地文档链接无缺失，十条来源/事件/状态逐项匹配已接受JSON；75个现有scripts/configs/evidence哈希未改，原vendor DDS差异逐字节保留，原R2冻结SHA不变。交接摘要evidence/linux-handoff-20261101.json，原始inventory/checks/references在run目录。
- 分项：本轮仅源码/文档和只读元数据准备passed；服务器安装、无界面控制和回放均awaiting_verification，现场相机needs_input，R4未实现。没有新Goal、服务器连接、计费资源或新增云费用；未复制凭据/账号配置/受限资产入Git。
