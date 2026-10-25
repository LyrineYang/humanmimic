# RTX 4060 与 Modal 资源方案

价格核对日为 2026-10-25，币种为 USD。用户资源为装有 WSL 的 RTX 4060 笔记本、32GB 系统内存，以及用户报告的 30 美元 Modal 额度。

## 4060 是否足够

4060 Laptop 的官方显存规格为 8GB。它值得直接用于单机器人 MuJoCo 和预训练 SONIC 的本地起步；GEM-X 与控制器并行的显存和实时速度需要实测，不能根据 GPU 名称承诺三项全部达到目标。此前建议的 24GB 是宽裕开发配置，不是已证实的最低要求。[NVIDIA 笔记本规格](https://www.nvidia.com/en-us/geforce/laptops/40-series/)

| 工作 | 首选位置 | 判断与处理 |
| --- | --- | --- |
| 源码、数据检查、关节参考整理 | 本地 WSL | 不需大显存 |
| 单个 G1 物理执行与录像 | 本地 4060 | 先关闭多余预览和高分辨率渲染，实测控制周期 |
| 短视频动作提取 | 先本地，必要时 Modal | batch 1，先短片；离线允许比视频时长慢 |
| 相机估计与控制并行 | 本地 4060 | 先分别测峰值，再测并行；窗口缩短可能损失稳定性，需要对照 |
| 场景修正的候选回放 | 本地 CPU 与4060，必要时 Modal | 候选先运动学筛选，再少量物理验证；不要求实时搜索 |
| 大规模 RL 或完整 SuperMimic 复现 | 首轮不安排 | 30美元不足以支持可靠的反复调试、对照和多种子复现承诺 |

系统的32GB内存不等于WSL可用32GB，先用 `free -h` 测量。项目与缓存优先放在 Linux 文件系统而不是 `/mnt/c`。[Microsoft 文件系统建议](https://learn.microsoft.com/en-us/windows/wsl/filesystems)

## WSL 部署检查

通过 Codex 执行 WSL 终端即可，不需要额外配置 SSH。当前 Mac 对话不能因此假定已有笔记本执行权限。

在 Windows PowerShell 查看 `wsl -l -v`；在 WSL 执行以下只读检查，保存输出：

```bash
uname -a
cat /etc/os-release
nvidia-smi
free -h
df -h .
ls /dev/video*
```

WSL2 可使用 Windows NVIDIA 驱动提供的 CUDA；不要在 WSL 中另装 Linux NVIDIA 显示驱动。TensorRT 与 CUDA 用户态依赖仍须匹配源码要求。[NVIDIA WSL 指南](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

分别验证 WSLg 图形、无界面渲染和相机读取。WSLg 支持 Linux GUI 不代表具体 MuJoCo 图形后端必然成功；GPU计算成功也不代表相机已暴露为 `/dev/video0`。[WSLg](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)

相机无法直接进入 WSL 时，先区分外接 USB 摄像头和内置摄像头。外接 USB 可以评估 usbipd 与内核驱动支持，但不能保证所有摄像头可用；另一个方案是在 Windows 采集帧，经本机网络送入 WSL，GEM-X 与控制器继续在 WSL 运行。后者需要单独实现采集桥接并计入延迟，不能称为已完成。[USB 接入说明](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)

## Modal 30美元能做什么

对当前以预训练推理为主的少量视频和仿真验证，30美元可以作为有用的补充预算；实际是否足够取决于首次运行耗时和依赖适配。不要先把它投入大模型训练或长期在线控制。

下表按普通 GPU Functions、默认地区、单 GPU、2个物理CPU核与8GiB系统内存持续占用计算。CPU 每核每秒0.0000131美元，内存每GiB每秒0.00000222美元，合计约0.1583美元/小时。费用在实际请求或使用更高、选择地区溢价、构建或加载增加时会上升。[Modal 价格](https://modal.com/pricing)

| GPU | GPU单价每小时 | 加上上述CPU与内存每小时 | 30美元理论时长 | 留5美元余量后的理论时长 |
| --- | ---: | ---: | ---: | ---: |
| L4 | 0.7992 | 0.9575 | 31.3小时 | 26.1小时 |
| A10 | 1.1016 | 1.2599 | 23.8小时 | 19.8小时 |
| L40S | 1.9512 | 2.1095 | 14.2小时 | 11.9小时 |
| H100 | 3.9492 | 4.1075 | 7.3小时 | 6.1小时 |

这是费用换算，不是项目耗时预测。内存配置是系统RAM，不是GPU显存；较重任务可能要请求更多RAM和CPU。优先比较 L4 与 A10 的每段视频成本；需要更多显存时才评估 L40S。H100 行只供理解预算，不属于默认运行配置。

存储、网络、镜像构建、加载、编译和容器收尾时间不包含在表内；余额、支付方式、可用机型与地区需要在账户中确认。冷启动及空闲保留时间也可能计费。[计费说明](https://modal.com/docs/guide/billing)

## 预算与执行规则

当前只授权调研与准备，没有启动计费任务。获得一次明确的已有额度内执行授权后，可按下表自主推进，不重复询问常规调用；不能超出额度或增加自付费用。

| 用途 | 预算上限 |
| --- | ---: |
| 镜像、驱动库、EGL与通信预检 | 1美元 |
| 参考动作无界面验证 | 5美元 |
| 离线视频动作提取 | 6美元 |
| 场景修正与对照 | 8美元 |
| 最终复验与导出 | 5美元 |
| 未分配余量 | 5美元 |

上述25美元工作额度是软件执行的软停止点；5美元余量留给计费延迟、构建与复验。配置文件不是平台硬限制，账本也不是实时余额API。启动前查看真实剩余额度与同工作区其他任务，不按用户最初报告的余额无限运行。

在 Modal 控制台核实 Workspace usage budget 与自付 spend limit：前者在抵扣额度前计算，后者限制抵扣后的自付支出。若账户支持，设自付上限0美元，并把usage上限设置为当前用量加允许的新用量；不能误以为初始30美元额度会自动阻止超额。Starter 不应依赖付费套餐才有的 Environment budget。[预算与自付限制](https://modal.com/docs/guide/budgets)

第一条 GPU 预检最长5分钟。后续默认一个容器、一张卡、任务最长15分钟，保留run ID、超时和成本估计。没有新证据不自动连续重试。GPU Function 可能因平台抢占重启，要用run ID避免重复输出并记录累计开销；显式重试次数设为0不代表平台永不重启。[抢占行为](https://modal.com/docs/guide/preemption)

优先普通短任务 Functions，不把长期 Sandbox 当成相同价格的开发机。模型缓存持久化后复用；不创建常驻在线服务。多个本地控制进程与MuJoCo在同一容器内的DDS通信、EGL/OSMesa渲染及启动退出都须先预检，再扩大量。云端导出的TensorRT engine不能假定可直接用于4060；将ONNX带回本地后按本机环境构建并验证。[TensorRT 兼容性](https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/support-matrix.html#software-and-system-requirements)

实时控制和相机优先本地；Modal保留为离线与无界面补充。公网流式演示即使能连接，也必须单独测延迟，不能当作本地实时验收。

## 来源与更新

下一次执行前重新核对价格、额度和软件版本。只在资源或价格改变时更新本文件与 configs/budget.json；实际支出记到运行记录，不改写为预算数。
