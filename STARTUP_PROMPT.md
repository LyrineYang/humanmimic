# HumanMimic 当前接续提示

更新于2026-11-02。本文件只保存当前入口；旧Mac/Windows、R2 Goal和迁移前提见[历史索引](docs/archive/README.md)。

1. 先读[AGENTS](AGENTS.md)、[PLAN](PLAN.md)当前状态/验收；具体实现看[HANDOFF](HANDOFF.md)，历史证据看[EXPERIMENTS](EXPERIMENTS.md)。核对当前Git、未提交修改、GPU占用和既有任务，避免重复提交。
2. 当前在Linux/V100服务器，R4独立环境已安装并完成干净重建/首跑。使用`source scripts/activate-r4-research.sh`；[准备指南](docs/getting-started.md)解释隔离、目录、锁文件和profile，入口为`humanmimic.py doctor/bootstrap/example/inspect`。不要因新会话重复安装。
3. R4沿用右LEAP、既定T1/T2、开发/保留划分与门槛；主线是显式多模态记忆→联合形状/位姿/顺应性估计→局部控制与探触。见[详细方案](docs/r4-multimodal.zh-CN.md)。P1/P2及记忆/控制已有V100工程证据；成功抓放、局部精化操作收益、置信区间校准、完整视频前端仍未完成。MANO已有授权，路径仍待提供。
4. R1/R2通过属于原4060/WSL；R2五条保留已使用。服务器R2目前只读诊断，正式执行保护未解除。R3本阶段跳过；不把静态箱体历史路线或旧迁移提示当作当前研究任务。
5. 整合提交e4c50ac与archive标签已按用户要求推送GitHub，后续以main为主线并按[REMOTE_WORK](REMOTE_WORK.md)核对。用户当前无法启动训练，E4读出拟合/E5暂缓；下一批非训练开发与计算/存储配额见[计划与预算](docs/r4-multimodal.zh-CN.md#11-当前实验计划与计算预算2026-11-02不启动训练)，不要自动启动完整矩阵。

继续已授权且可行的工作；只做仿真，不从零训练、不用保留调参、不启用计费资源、不连接真机、不改驱动、不用CPU数值替代。源码/标准库契约、CUDA数值、无界面物理、录像与相机分别报告。每次修改先记录预期，受影响路径复验，历史失败及资产/源码哈希保留；更新PLAN与EXPERIMENTS。没有新明确目标请求时不自动创建Goal。
