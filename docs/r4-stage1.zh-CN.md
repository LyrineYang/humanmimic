# R4 第一阶段：局部几何精化与灵巧操作的因果对照

制定日期：2026-11-01；运行准备结果更新于2026-11-02。用户已授权本机环境配置和运行准备，并希望补齐 VideoManip 下游未公开流程。当前交付是具体方案、独立运行栈、接口/评价实现与小规模就绪验证；正式保留集仍不用于调试。不从零训练、不使用付费 API、不连接真机、不更改系统驱动。

> 2026-11-02新增：用户要求研究WM-CraftNet的多模态记忆与触力觉，详见[源码审计、实现计划和探究实验](r4-multimodal.zh-CN.md)。沿用本文手型/任务/门槛；新增观测分组及几何×力反馈对照，不把增加模态的收益混入原几何算法对比。

## 1. 第一阶段的确定选择

| 项目 | 选择与理由 |
| --- | --- |
| 手型 | **右手 LEAP Hand，16个独立手指关节**。采用 MuJoCo Menagerie 固定版本；和 VideoManip 论文的真实操作手型有联系，资产开放、关节明确。当前作者示例默认使用 Inspire，不能直接把其输出当LEAP关节 |
| 执行平台 | MuJoCo 3.2.7；自由腕部由有力/力矩上限的PD控制器驱动，16关节位置伺服；物体始终由重力、接触和摩擦运动 |
| 任务T1 | 抓取→抬升80mm→持续保持2秒；抬升采样中至少80%同时存在拇指和其他手指的有效接触（法向力>0.05N） |
| 任务T2 | 在T1基础上平移80mm、偏航30°、释放并静置1秒；静置窗口全程无手部接触，位置≤5mm、姿态≤5°才算精度达标 |
| 主数据 | **R4-LocalGeom-v1可控对象集**：四类刚体，12个开发实例、24个保留实例，实例seed分离；完整真值仅给渲染器和评价器 |
| 实拍外部验证 | **DexYCB**：单路RGB输入，标定/深度/CAD单独封存作评价；另列RGB-D诊断分组，不能混称纯RGB能力 |
| 视频接口开发样例 | 作者发布的 `real_14_pourtea.mp4` 只作输入/解码诊断，不纳入主任务成功率，不把倒茶自动当作上述放置任务 |
| 首阶段主问题 | 固定手型、控制器、动作与预算，几何精化是否减少实际目标误差及失误；不同时引入新的学习策略掩盖几何贡献 |

Menagerie 资产固定提交 `b0655057a9df2abe39ea7fc989914ba6f248301c`，LEAP目录的21个必要文件已独立下载并校验Git blob与SHA256；许可保留在资产目录。VideoManip源快照固定 `9d0f286af35d73f4252d115d968e0a9c06542b9c`，位于数据目录，未改其仓库。

这不是全身G1验收，也不证明真实手臂可达性。腕部虚拟执行机构的力上限和轨迹跟踪误差需报告；不通过直接写手/物体qpos制造成功。

## 2. 数据划分与任务细节

### 可控对象集：先隔离几何原因

四类对象为阶梯肩部棱柱（stepped_prism，明确不是光滑倒角）、局部凹槽块体（grooved_block）、带肩部/细颈的柱体（necked_column）、U形开口把手（u_handle，明确不是闭合环）。每类3个开发实例和6个保留实例；尺寸、局部厚度和槽宽不同，实例整体分组，不把同一对象的不同帧拆到开发和保留。

开发seed为101–112；保留seed为201–224；每个对象的正式执行种子为1101/1102/1103。准备测试另用编号 `readiness-*`，不读取保留几何或计算保留结果。正式主对照为24对象×2任务×3种子×6方法=864次执行；失败也保留在分母，准备阶段不启动这批任务。

输入分成两条明确报告的轨道：

1. **机制诊断轨道：** 从独立真值生成带噪表面观测/遮挡及受控粗模型，保证每个方法拿到相同观测。它回答局部几何误差是否影响操作，不声称完成了单目重建。
2. **视频轨道：** 视频中实际提取的物体网格、姿态、手部轨迹作为输入；替换感知前端后重复相同对照。只能在这条轨道通过后声称“视频重建改善了操作”。纯RGB无尺度锚与有标定/尺度锚条件分开。

每个对象先冻结目标位姿和任务容差。场景中禁止将待执行物体焊接到手上；允许腕部执行机构作为声明的模型，但需要力矩限制。薄壁/孔洞用多个凸部件或原始解析形体表达，不能悄悄用覆盖孔洞的单凸包替代。

### DexYCB：固定筛选规则，不按结果挑片

实拍开发组使用subject-01，保留组使用subject-02；目标对象固定为 `005_tomato_soup_can`、`008_pudding_box`、`009_gelatin_box`、`010_potted_meat_can`、`025_mug`。开发每对象取按sequence名排序的首2个右手完整抓取序列；保留每对象取首4个，最多10开发/20保留。相机统一使用序列元数据中按序列号排序的首路RGB，完整帧轴保留。缺少对应对象/右手/有效标定时明确记缺失，不按执行效果补换。

下载后先用元数据生成含具体sequence/frame/相机/来源SHA的清单并冻结；**在这份实例清单生成前，实拍正式运行入口不得放行**。本方案不是DexYCB官方排行榜协议，不把自定义子集结果冒充官方分数。它也不是未见对象测试：对象几何可能跨subject相同，未见对象结论主要依靠可控实例划分及后续单独冻结的对象组。

DexYCB自身是人手抓取数据，不提供本项目机器人精密放置的真值动作。T1可用视频接触/手姿态启动；T2的机器人目标由本项目预先定义，报告为任务迁移。数据受CC-BY-NC-4.0约束，不入Git。MANO用户已确认拥有授权，路径待提供。

## 3. 要补齐的VideoManip下游

作者当前发布重建、可选ContactOpt包装与重定向入口，未完整发布抓取训练/操作策略流程。本项目实现独立下游，区分“兼容其重建接口”与“复现未公开的论文算法”。

| 环节 | 第一阶段做什么 | 完成标准 |
| --- | --- | --- |
| 数据入口 | 读取数值 `robot_qpos.npy` 与 `robot_qpos_index.npy`，绑定完整源时间戳、手型/关节名、世界坐标变换、网格与来源SHA | 拒绝默认Inspire输出、缺坐标约定、缺时间戳和不匹配关节；不允许pickle数据执行 |
| 标准中间格式 | 保存明确的米/弧度、wxyz四元数、参考/实际角色、原始帧索引和数据划分 | 单元与坐标转换可核对，不静默裁剪帧或角度 |
| 几何处理 | 统一粗网格及碰撞代理；根据同一观测拟合局部接触表面 | 可见与推断区域分开；几何指标和碰撞代理误差同时输出 |
| 动作生成 | 保留重定向轨迹作为原始基线；接触约束IK和有限候选物理优化作为独立模块 | 所有方法共享参数、种子和调用预算；优化只访问规划模型 |
| 实际执行 | 参考经过控制器→动力学；保存实际手/物体状态、接触、力矩、失败和视频 | 不逐帧覆写实际状态，不从目标轨迹直接生成“执行录像” |
| 评价/数据导出 | 每次输出来源/配置/版本、指标、完整轨迹与演示数据接口 | 同时记录失败，给未来策略学习提供真实执行数据，而不是仅存运动学标签 |

策略训练、DemoGen式数据扩增和模仿策略学习是后续模块；本轮不从零训练。补齐第一阶段重点是可独立核验的几何—动作—物理执行—评价链路，为后续学习提供可用数据与基线。

特别注意：源代码注释将基座角度称为axis-angle，但底层虚拟旋转关节也可能使用Euler语义。导入必须显式指定旋转表示，并通过FK对照确认，不能自动猜测。LEAP关节编号映射为 `[1,0,2,3,5,4,6,7,9,8,10,11,12,13,14,15]` 对应Menagerie的MCP/旋转/PIP/DIP顺序；不得按数字排序直接拷贝。

## 4. 基线与消融

| 方法 | 改动 | 目的 |
| --- | --- | --- |
| coarse | 同一粗模型，直接使用原始重定向/统一规划器 | 起点 |
| uniform | 对全物体均匀分配精化资源 | 判断收益是否仅来自额外计算 |
| random_local | 随机选择同面积局部，固定seed | 排除任意局部精化都有效 |
| contact_local | 根据估计接触选区 | 强对照：接触细化本身已有研究 |
| task_local | 接触概率×任务对局部误差的敏感度选区 | 主方法；对几何、尺度和执行误差的传播建模 |
| oracle_geometry | 独立真值几何，控制器不变 | 仅诊断上界，不作为可部署方法 |

task_local消融去掉表面法向约束、去掉接触权重、故意偏移ROI；保持顶点更新数/观测数/步数相同。先不增加世界模型或策略网络，以保持主因果问题可解释。

每对象固定32768条可用表面观测、最多4096条精化观测、2048个可更新顶点、200步优化；规划64候选、最多128次rollout、总墙钟上限300秒。两种预算视角都报告：固定操作数主对照，以及按同GPU墙钟/显存核对的补充对照。超时、拒绝和失败计入成本；不能只统计成功候选。

## 5. 指标、统计与判定

- 几何：接触ROI表面距离中位数/P95（mm）、法向误差、槽宽/厚度误差；另报全局Chamfer、尺度和物体6D姿态误差。
- 操作：T1抬升/保持成功，T2最终平移和转角误差、5mm/5°成功、滑落、穿透峰值与持续时间、控制饱和、拒绝率。最大穿透超过2mm视为物理有效性失败。
- 不只对成功样本统计精度：失败计入成功率分母，并使用预先声明的100mm位置惩罚计算全样本目标误差，同时保留未经惩罚的原始距离。
- 主张标准：task_local相对coarse的配对全样本位置误差降低至少20%，对象级bootstrap 95%区间下界>0；同时相对uniform的误差差异区间支持改善，成功率差异下界不得低于−5个百分点。若只改善粗基线、不能优于uniform，就不支持任务分配的额外价值。
- 每对象跨种子汇总后再bootstrap，避免把相邻帧当成独立样本。开发中确认度量实现和任务可达；正式运行前冻结配置/代码/资产/种子与测试清单。不能看过保留结果再改阈值。

正式结论可以是支持、部分支持或否定假设。准备完成不等于方法有效，负结果也不通过降低门槛改写。

## 6. V100环境与磁盘方案

数据根为 `/home/junqiy/projects/humanmimic-data/r4`，代码位于独立仓库目录。独立Python 3.10.14由官方校验后的Miniforge 24.3离线包配置；不使用系统Python3.6或旧R1/R2环境。选Torch2.5.1+cu118和MuJoCo3.2.7，避免引入TensorRT、FlashAttention-2或新Warp作为前置条件。MuJoCo物理首先跑CPU，GPU用于张量/几何和EGL渲染，分别实测，不能把可见GPU当计算通过。

依赖入口为 `configs/requirements-r4-core.txt`，激活入口为 `scripts/activate-r4.sh`。安装后保存精确pip/Conda锁定与原始安装报告。使用一张检查后空闲的V100，初始CPU线程8、数据占用上限40GiB、数据卷剩余下限100GiB；不抢占其他任务，四卡并行不是本阶段必要条件。

`envs/`、`assets/`、`sources/`、`cache/`、`tmp/`、`datasets/`和`runs/`都放数据根；不把模型、MANO、视频或账号配置写入Git。当前网络经用户反向代理，具体可用性与配置写入本轮run记录，代理凭据不入文档/脚本。安装入口不应自动替换全局代理。

## 7. 本轮就绪清单

1. 环境：依赖冲突检查、V100 SM70实际矩阵计算、有限值/CPU对照、峰值显存、动态库和版本快照。
2. 资产：LEAP MJCF及全部mesh解析，16关节名/方向/范围与VideoManip的URDF核对；录像输入全解码，MANO路径单独核验。
3. 接口：合成fixture验证转换，错误手型/非刚性变换/时间戳不单调/关节超限必须拒绝；fixture不计为真实视频重建。
4. 物理：小规模准备场景完成实际动力学步进、接触及控制记录，生成实际状态视频；分别报告“能运行”和“抓取/放置成功”。
5. 隔离：不访问正式保留输入，旧脚本/配置/evidence等受保护文件不改（本轮扩展保全检查覆盖82个文件）；新R4配置和证据独立记录。

当前运行状态和产物以PLAN、EXPERIMENTS及 `runs/r4-stage1-preparation-20261101-01/` 为准。准备验收结果如下：

| 分项 | 状态与证据边界 |
| --- | --- |
| 核心依赖与V100计算 | passed；Python3.10.14、Torch2.5.1+cu118、MuJoCo3.2.7、CoACD1.0.5；pip check正常，实际SM70计算最大绝对误差3.08×10⁻⁵ |
| 手型映射 | passed；64项独立URDF/MJCF正运动学对照，最大位置差5.04×10⁻⁸m。修复了源URDF基座到掌心的固定平移/180°旋转；初次失败保留 |
| 输入与评价实现 | passed；17项测试覆盖关节顺序、坐标、时间戳、pickle拒绝、保留集隔离、松手判定、静置误差和穿透。正向评价fixture不是实际操作成功证据 |
| 无界面物理与实际录像 | passed（运行基础）；最终负对照2000步/4秒，101帧真实状态录像，V100 EGL渲染。任务failed符合预期：没有抓到物体，80mm/30°目标误差，不能计作成功抓取 |
| 开发数据 | 12个解析对象与每对象24视角/32768点RGB-D合成观测已生成；深度噪声标准差0.5mm。法向来自模拟深度差分，不能称为RGB估计；保留实例未生成、未使用 |
| 网格碰撞入口 | passed（接口）；CoACD凸分解、SHA校验和MuJoCo实际步进已连通。碰撞近似的毫米级误差尚未全面审计；复合体当前按部件等质量分配，正式对照前要冻结同一质量/惯量并做敏感性检查 |
| DexYCB实拍 | awaiting_verification；已取得标定，序列/CAD尚未下载，具体序列清单尚未冻结 |
| MANO/完整视频前端 | needs_input（MANO路径）；用户已授权持有资产，稍后提供。HaMeR/SAM2/MoGe/FoundationPose子环境、权重和端到端输出仍awaiting_verification，不是只差一个MANO路径 |
| 局部精化、规划与主假设 | awaiting_verification；六方法/消融是已确定实施方案，优化器、抓取规划器及正式统计尚未实现，不能宣称操作精度提升 |
| 动画/现场相机 | 合成输入旋转录像通过；它不是机器人动作验收。物理录像由当次实际状态在线渲染，独立缓存重放尚未验收；现场相机本阶段不运行 |

## 8. 本机复跑入口与安装记录

已安装环境位于 `/home/junqiy/projects/humanmimic-data/r4/envs/r4-core`，当前无需重新安装。源代码/配置在仓库，依赖、外部源仓库和资产在相邻数据根，不形成仓库嵌套。精确Conda记录见 `configs/conda-r4-linux-64.explicit.txt`；`configs/requirements-r4-core.lock.txt` 是安装后Python包版本清单，包含Conda自带包，**不是供pip全量重装的requirements**。

网络已经修复：安装命令显式使用用户提供的 `socks5h://127.0.0.1:7893`。此前环境自动注入的27891代理返回403；7893实际GET/下载成功。仅在本次下载命令设置代理，未更改全局代理、驱动、系统Python或shell启动文件。首次安装器因 `~/.conda` 注册权限失败，获准宿主运行后成功，原日志保留。

重建同等核心栈时，用已验证SHA的Miniforge24.3安装包配置独立前缀，随后执行以下命令；仅适用于已经确认7893转发可用的这台机器：

```bash
source scripts/activate-r4.sh
python -m pip install --proxy socks5h://127.0.0.1:7893 -r configs/requirements-r4-core.txt
python -m pip install --proxy socks5h://127.0.0.1:7893 torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu118
python -m pip check
```

按当前占用选空闲GPU，设置CUDA UUID与对应EGL物理索引；不要复制历史空闲判断。首次计算验证用GPU1，最终录像复验时它已被其他任务使用，因此使用GPU3；这两次是环境准备，不构成跨硬件方法对照。正式对照固定同一GPU。

```bash
source scripts/activate-r4.sh
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu --format=csv
# 按刚检查的空闲卡填写 CUDA_VISIBLE_DEVICES=GPU-... 与 MUJOCO_EGL_DEVICE_ID=物理索引
# 以下入口拒绝覆盖已存在目录；使用新的唯一 RUN 路径。
R4_RUN="$R4_DATA_ROOT/runs/readiness-$(date -u +%Y%m%dT%H%M%SZ)"
python scripts/prepare-r4-readiness.py --output "$R4_RUN/input"
python scripts/run-r4-physical.py --reference "$R4_RUN/input/reference.json" --evaluation-scene "$R4_RUN/input/evaluation-scene.json" --output "$R4_RUN/physical" --render
python -m pytest -q tests
```

这个fixture有意让手不抓物体，预期 `execution_status=passed`、`task_status=failed`。物体目标误差、接触、力、关节和腕部实际状态、来源SHA、完整MP4均在输出目录；它用于检查动力学/失败判定，不能作为操作baseline成绩。

其他入口：`prepare-r4-objects.py --output <新目录>`生成12个开发对象；`render-r4-observations.py --scene <evaluation.json> --output <新目录>`生成该对象观测；`prepare-r4-collision.py --mesh <米制闭合OBJ> --scene-template <声明角色的JSON> --output <新目录>`生成凸部件。这些入口拒绝保留集。算法只能读取观测与规划资产，评价几何由独立进程/接口使用；当前文件夹是研究角色约定，尚不是安全沙箱。

导入实际VideoManip输出使用：

```bash
python scripts/import-r4-videomanip.py --qpos /absolute/robot_qpos.npy --indices /absolute/robot_qpos_index.npy --timestamps /absolute/source_timestamps.npy --metadata /absolute/source_metadata.json --source-urdf /absolute/leap_hand_right.urdf --output /absolute/reference.json
```

metadata必须显式包含：`hand=leap_right`、原关节名顺序、`kind=video_reconstruction`、`split=debug`、`units={length:m,angle:rad}`、`base_rotation=rotvec`或`euler_XYZ_intrinsic`、`wrist_frame=urdf_base`或`palm`、实际 `T_world_source` 4×4刚体变换、`source_video`和`source_commit`。这些值须从真实输出核实，不提供一份全填identity的伪通用配置。timestamps来自源视频完整PTS；缺失帧保留原索引，不能用连续帧号掩盖。上游默认Inspire路径不能直接喂入。

## 9. 从当前基础到正式验证的执行顺序

1. **M0 已完成：** 独立核心栈、LEAP映射、合成输入、网格碰撞、参考契约、实际物理运行与失败评价。完整视频感知不属于已通过内容。
2. **M1 开发基线：** 从同一观测拟合粗模型，确定固定接触约束IK/64候选/128rollout规划器；先用开发对象和oracle_geometry确认T1/T2可达。输出无接触/夹持不放/漂移等负对照；若oracle也无法完成任务，先定位控制与惯量问题，不归因于重建。
3. **M2 局部精化：** 在相同粗网格与观测上实现六方法及三消融，优化数据项、法向项与形变正则；统一顶点/观测/步数预算。ROI只从估计几何、接触与任务扰动敏感度生成，禁止访问真值选区。输出更新mask、采样索引、优化轨迹和几何误差。
4. **M3 开发物理对照：** 固定控制器/动作来源/物理参数和GPU，执行12开发对象。确认局部几何误差与实际误差关系、全部失败归因、碰撞代理误差、摩擦/质量鲁棒性和墙钟预算。计划动作可随几何优化，优化器与初始动作/候选seed保持相同；不要求各方法最终轨迹相同。
5. **M4 视频接通：** 接收MANO路径，独立建立VideoManip前端子环境与权重。逐段验证手部、分割、尺度/位姿及LEAP重定向，再使用本项目导入接口。其原stage6需付费API，当前采用本地重建/受控粗模型适配；不能用DexYCB真值CAD假冒单目估计。FoundationPose官方Docker路径受宿主权限限制，需单独验证用户态构建或另选已审计本地姿态模块，当前未通过。
6. **M5 冻结与正式结论：** 开发指标/代码/预算/输入清单冻结后，才物化24个保留对象并记录首次使用；主对照864次与消融另建运行清单和总成本估计。当前准备授权不包含这批正式运行。输出全样本统计、所有失败与三路可追溯演示，支持或否定假设均如实报告。

当前没有理由从零训练：先确认几何和固定控制的因果收益，再决定是否用真实执行数据补齐训练/策略学习模块。

## 来源

- [VideoManip源码与发布范围](https://github.com/hychen-naza/VideoManip)、[重定向接口](https://github.com/hychen-naza/VideoManip/tree/main/reconstruction/dex_retargeting)
- [LEAP Menagerie模型](https://github.com/google-deepmind/mujoco_menagerie/tree/main/leap_hand)
- [DexYCB官方数据与许可](https://dex-ycb.github.io/)
- [PyTorch版本安装说明](https://pytorch.org/get-started/previous-versions/)、[MuJoCo 3.2.7](https://pypi.org/project/mujoco/3.2.7/)
- [上轮详细研究与边界](research-video-interaction.zh-CN.md)
