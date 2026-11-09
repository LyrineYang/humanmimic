# 当前接续：GitHub推送与本地接手

最新用户要求：停止新增打包及复杂核验，完成GitHub推送、内容更新和报告。先读`docs/migration-20261109/README.md`和`delivery-status.json`；代码/精选演示在main，已有大文件附件在同仓库草稿Release。不要恢复已取消的完整解包核验任务。pilot04开发收益仍未达门槛，8201–8206未使用；先完成目标机环境和状态恢复验证，不启动新训练或showcase。原预算窗口与账本不能随迁移重置。

# HumanMimic 当前接续提示

最新任务：优先稳定握持/载荷转移/低扰动释放，再比较early/supported单次探触；保存成功与失败的raw视频，showcase仍禁止。同8GPUh账本，初始余量7.6536h；新目录runs/vividex-release-timing-20261109-01，先查活跃任务。允许公共工程技巧，不做不公平baseline对照。以PLAN首节为准。

最新澄清与任务（2026-11-09）：把接触校正接入ViViDex真实自由物体的放置阶段；两组固定权重、同观测/同探触预算，评价释放后误差。预算用原story-contact-20261109剩余额度，不重置。原“不生成视频”只禁止showcase合集，raw实验演示可录；默认仍无录制。见PLAN最新段与runs/vividex-contact-integration-20261109-01/。

当前结果：接入和60分支归档核验passed；30对主指标25.640→24.580mm，4.14%改善/16对合格，研究门槛failed。无活跃作业；本轮新增0.2286GPUh，8h台账剩7.6536。7101–7106已用，不再称未见测试。下一步检查握持/支撑切换与探触时机，原LEAP/E3门槛不变。

更新于2026-11-09。本文件只保存当前入口；旧Mac/Windows、R2 Goal和迁移前提见[历史索引](docs/archive/README.md)。

0. 最新范围覆盖下方旧运行快照：用户新授权8 GPU小时、故事优先、只做预训练推理/仿真。按configs/budget.json#local_demo_campaign独立记账，不恢复旧144卡时campaign。问题为“一次接触校正物体相对手的任务方向偏差”，DexTrack LEAP资产不可得则切ViViDex；见PLAN顶部。只共享GPU0并保留外部进程；每个作业经run-r4-prerequisite-job.py --budget-section local_demo_campaign --stage对应阶段 --parallel 1启动，数值与渲染均计时。

当前视频约束：允许原始实验演示录像，禁止showcase合集；video_generation_authorized=true、showcase_generation_authorized=false，运行默认无录制。现有结果与失败保留。接触残差已接入ViViDex，最终效果以冻结验证报告为准，不能将松手前收益当作放置精度收益。


1. 先读[AGENTS](AGENTS.md)、[PLAN](PLAN.md)当前状态/验收；具体实现看[HANDOFF](HANDOFF.md)，历史证据看[EXPERIMENTS](EXPERIMENTS.md)。核对当前Git、未提交修改、GPU占用和既有任务，避免重复提交。
2. 当前在Linux/V100服务器，R4独立环境已安装并完成干净重建/首跑。使用`source scripts/activate-r4-research.sh`；[准备指南](docs/getting-started.md)解释隔离、目录、锁文件和profile，入口为`humanmimic.py doctor/bootstrap/example/inspect`。不要因新会话重复安装。
3. R4沿用右LEAP、既定T1/T2、开发/保留划分与门槛；主线是显式多模态记忆→联合形状/位姿/顺应性估计→局部控制与探触。见[详细方案](docs/r4-multimodal.zh-CN.md)。P1/P2及记忆/控制已有V100工程证据；成功抓放、局部精化操作收益、置信区间校准、完整视频前端仍未完成。MANO已有授权，路径仍待提供。
4. R1/R2通过属于原4060/WSL；R2五条保留已使用。服务器R2目前只读诊断，正式执行保护未解除。R3本阶段跳过；不把静态箱体历史路线或旧迁移提示当作当前研究任务。
5. 历史144卡时窗口（已结束，不能作为新授权）：当时允许共享GPU0、保留其他用户进程，今晚24:00前优先前置与持久队列，不再等待四卡空闲。144卡时/36连续墙钟小时窗口已经开始，续跑不重置；前置8、E1 12、E2 18、E3 72、余量34。预算以`configs/budget.json`的local_r4_campaign为准，协议见[第12节](docs/r4-multimodal.zh-CN.md#12-e3优先的144卡时执行方案2026-11-02)。本轮队列已结束，先读`runs/r4-prerequisites-overnight-20261103-02/session/result.json`和数据目录`runs/r4-e3-development-20261102/ledger.json`；不要把旧PID38649/40617或最后progress快照当活跃任务。累计3.0270卡时；窗口2026-11-03 20:54:06至11月5日08:54:06北京时间。局部完整手40试次、P1/P2、31项控制及在线负对照工程回归通过；条件平移20拟合/20独立验证为18/20，解析xyz/C覆盖20/20。旧U形T1/T2虽通过，但超2N且源码已变；当前低力抓放和完整SE3/物体顺应性联合校准仍未过，E3与学习训练未启动。倍率仅用于离线评价，未接入在线协方差；继续接触约束参考优化和真实联合校准，不调已用验证种子。新插件只用项目独立native_plugins。

继续已授权且可行的工作；只做仿真，不从零训练、不用保留调参、不启用计费资源、不连接真机、不改驱动、不用CPU数值替代。源码/标准库契约、CUDA数值、无界面物理、录像与相机分别报告。每次修改先记录预期，受影响路径复验，历史失败及资产/源码哈希保留；更新PLAN与EXPERIMENTS。没有新明确目标请求时不自动创建Goal。
