# HumanMimic 当前接续提示

更新于2026-11-03晚间。本文件只保存当前入口；旧Mac/Windows、R2 Goal和迁移前提见[历史索引](docs/archive/README.md)。

1. 先读[AGENTS](AGENTS.md)、[PLAN](PLAN.md)当前状态/验收；具体实现看[HANDOFF](HANDOFF.md)，历史证据看[EXPERIMENTS](EXPERIMENTS.md)。核对当前Git、未提交修改、GPU占用和既有任务，避免重复提交。
2. 当前在Linux/V100服务器，R4独立环境已安装并完成干净重建/首跑。使用`source scripts/activate-r4-research.sh`；[准备指南](docs/getting-started.md)解释隔离、目录、锁文件和profile，入口为`humanmimic.py doctor/bootstrap/example/inspect`。不要因新会话重复安装。
3. R4沿用右LEAP、既定T1/T2、开发/保留划分与门槛；主线是显式多模态记忆→联合形状/位姿/顺应性估计→局部控制与探触。见[详细方案](docs/r4-multimodal.zh-CN.md)。P1/P2及记忆/控制已有V100工程证据；成功抓放、局部精化操作收益、置信区间校准、完整视频前端仍未完成。MANO已有授权，路径仍待提供。
4. R1/R2通过属于原4060/WSL；R2五条保留已使用。服务器R2目前只读诊断，正式执行保护未解除。R3本阶段跳过；不把静态箱体历史路线或旧迁移提示当作当前研究任务。
5. 最新授权：允许共享GPU0、保留其他用户进程，今晚24:00前优先前置与持久队列，不再等待四卡空闲。144卡时/36连续墙钟小时窗口已经开始，续跑不重置；前置8、E1 12、E2 18、E3 72、余量34。预算以`configs/budget.json`的local_r4_campaign为准，协议见[第12节](docs/r4-multimodal.zh-CN.md#12-e3优先的144卡时执行方案2026-11-02)。本轮队列已结束，先读`runs/r4-prerequisites-overnight-20261103-02/session/result.json`和数据目录`runs/r4-e3-development-20261102/ledger.json`；不要把旧PID38649/40617或最后progress快照当活跃任务。累计3.0270卡时；窗口2026-11-03 20:54:06至11月5日08:54:06北京时间。局部完整手40试次、P1/P2、31项控制及在线负对照工程回归通过；条件平移20拟合/20独立验证为18/20，解析xyz/C覆盖20/20。旧U形T1/T2虽通过，但超2N且源码已变；当前低力抓放和完整SE3/物体顺应性联合校准仍未过，E3与学习训练未启动。倍率仅用于离线评价，未接入在线协方差；继续接触约束参考优化和真实联合校准，不调已用验证种子。新插件只用项目独立native_plugins。

继续已授权且可行的工作；只做仿真，不从零训练、不用保留调参、不启用计费资源、不连接真机、不改驱动、不用CPU数值替代。源码/标准库契约、CUDA数值、无界面物理、录像与相机分别报告。每次修改先记录预期，受影响路径复验，历史失败及资产/源码哈希保留；更新PLAN与EXPERIMENTS。没有新明确目标请求时不自动创建Goal。
