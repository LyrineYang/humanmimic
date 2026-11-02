# Windows WSL 与跨设备协作

本项目优先让Windows笔记本提供GPU和WSL环境，Mac通过Codex远程控制查看、指导和验收同一执行端。不要把“登录同一账号”“控制另一台主机”“迁移聊天和Git状态”混为一项操作。

2026-10-28 Git 同步核验：私有仓库 `https://github.com/LyrineYang/humanmimic` 已存在，WSL 的 gh 登录、fetch、R1 内容 push 及从 GitHub 新克隆已通过。本轮命令需临时移除指向不可用本地端口的代理变量；未更改持久代理或账号配置。Git 同步与聊天 handoff 分别验收，后者未重试。

## Windows 应用能否操作 WSL

可以。Windows原生代理默认在PowerShell执行，也能按需调用 `wsl`。如果主要工作是Linux、CUDA和机器人仿真，建议在桌面应用Settings中把agent从Windows native切到WSL，并重启应用，然后打开WSL项目目录。

集成终端与agent的设置互相独立。仅把终端选成WSL，不能证明代理本身已在WSL执行。开始前让代理报告 `uname -a`、`pwd` 与 `nvidia-smi`。

添加WSL项目时，可在添加项目的文件选择器输入 `\\wsl$\`，选择Linux发行版和 `home/<user>/projects/humanoid-demo`。WSL代理搭配Linux文件系统；若坚持用Windows原生代理，官方建议项目保存在Windows盘并通过 `/mnt/<drive>/` 访问，两种布局不要混用。

来源：[Windows桌面应用与WSL](https://learn.chatgpt.com/docs/windows/windows-app#windows-subsystem-for-linux-wsl)。

## 用 Mac 控制 Windows 上的执行聊天

1. Windows和Mac使用同一ChatGPT账号及同一workspace，保持应用更新。
2. Windows应用进入Settings → Connections → Control this Mac or PC，完成启用和验证。
3. Mac应用若有Control other devices入口，通过它添加并配对Windows主机。入口可用性随发布范围而变化；没有入口时不要假设同账号已自动连接。
4. 连接后选择Windows主机上的WSL项目与聊天。该聊天使用主机的文件、工具、凭据和权限；Mac是控制端。
5. 同一执行聊天只保留一条有序工作流。检查任务状态后再补充指令，不在两台机器上重复启动同一实验。

主机休眠、断网或关闭应用会中断远程访问。需要桌面交互时，Windows还需处于可用的交互会话。来源：[远程连接](https://learn.chatgpt.com/docs/remote-connections)。

## 当前 Mac 聊天如何继续到 Windows

有两条路径：

- 远程接管Windows已有聊天：保持该聊天在Windows执行，Mac查看和发送指令。它不等于迁移当前Mac聊天。
- Handoff当前聊天：先连接Windows主机，并在两端保存同一个Git仓库对应的项目；然后由用户在聊天底部选择目标运行位置并确认Hand off。应用转移聊天与Git状态，目标端建立或复用工作树。若工具从当前聊天发起，不能把自身交接出去，应由用户使用界面，或从另一个已获授权的聊天发起。

2026-10-26 实测：Mac 已可访问远端主机 `zhen`，Windows 项目目录为 `C:\Users\Oscar\Desktop\humanoid-demo-remote`，但该目录尚不是 Git 仓库；`/home/lyrine/projects/humanoid-demo` 不存在。WSL2、Ubuntu 24.04.4 与 WSL 内 nvidia-smi 已通过检查，当前代理仍从 Windows PowerShell 发起命令。先建立对应的 Git 工作副本、登记同仓库项目，再确认 Handoff 目的地可选；代理切换 WSL 尚未执行。不要为了匹配主机而随意公开仓库或上传凭据。证据：`runs/preflight-20261026-remote/results.json`。来源：[聊天跨主机交接](https://learn.chatgpt.com/docs/remote-connections#hand-off-a-chat-between-hosts)。

## 同账号不等于同步所有本地内容

2026-10-28 已实测当前代理直接在主机 zhen 的 Ubuntu/WSL2 内执行，工作目录 `/home/lyrine/projects/humanoid-demo` 是 Git 工作副本。`humanoid-r1` conda、CUDA/TensorRT/ONNX Runtime C++ 环境、默认 SONIC 权重和官方控制器已配置，通过一次 1375 帧 Macarena 闭环物理复现；激活命令为 `source scripts/activate-r1.sh`。WSL 本机大 UDP 包丢失通过项目内 DDS 小包分片与 lo 单播配置解决，未改系统网络。离屏录像使用 CPU 软件路径，图形窗口与现场相机未验收。此前“目录不存在、仅从 Windows 调用 WSL”是历史状态；本次副本未带入旧 `runs/` 证据。当前证据：`runs/r1-full-setup-20261028/results.json`、`runs/r1-reproduction-20261028-01/REPORT.md`。

远程连接让你访问主机上的聊天和项目，不是把所有设备的磁盘、模型、环境和会话目录互相复制。代码用Git同步，运行结果保存到约定位置，现场资源由实际执行主机提供。

Windows原生应用通常使用 `%USERPROFILE%\.codex`，WSL CLI默认使用Linux家目录下的 `~/.codex`；两者默认不共享配置、认证缓存和历史。官方提供本机共享Codex home的方法，但本项目不需要先手工同步这些内部目录。不要把Mac、Windows和WSL的整个 `.codex` 目录当项目文件同步。

来源：[Windows与WSL的配置和会话](https://learn.chatgpt.com/docs/windows/windows-app#share-config-auth-and-sessions-with-wsl)。
