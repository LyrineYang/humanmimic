# Windows WSL 与跨设备协作

本项目优先让Windows笔记本提供GPU和WSL环境，Mac通过Codex远程控制查看、指导和验收同一执行端。不要把“登录同一账号”“控制另一台主机”“迁移聊天和Git状态”混为一项操作。

2026-10-28 当前安排：优先 handoff 原聊天到已登记的远端项目 `/home/lyrine/projects/humanoid-demo`。首次实际迁移因 Git origin 无法匹配而失败。用户已授权创建并推送私有仓库 `https://github.com/LyrineYang/humanoid-demo`；私有仓库已创建，本地 CLI 授权及首次 main 推送均已完成。远端 origin 也已配置为同一 URL；WSL 的 git ls-remote 因缺少 HTTPS 认证退出128，gh 尚未安装。配置认证后验证私有仓库访问；handoff 仍需从另一个聊天或应用界面重试，不能把 URL 配置成功当成迁移完成。

## Windows 应用能否操作 WSL

可以。Windows原生代理默认在PowerShell执行，也能按需调用 `wsl`，现有预检已验证这条路径。建立 WSL 文件系统中的副本、将 agent 切换为 WSL 是推荐配置，不是开始仿真的硬性前提。如果主要工作是Linux、CUDA和机器人仿真，建议在桌面应用Settings中把agent从Windows native切到WSL，并重启应用，然后打开WSL项目目录。

2026-10-26 当前工具能力：可通过远端聊天执行命令、准备项目文件和验证结果；没有修改 Windows 应用 agent 选择器的工具接口，且 Computer Use 禁止操作 Codex 应用界面。因此项目文件准备可由代理代办，Windows 应用内切换与重启需要用户操作；不能通过修改未文档化的内部配置冒充完成设置。

集成终端与agent的设置互相独立。仅把终端选成WSL，不能证明代理本身已在WSL执行。开始前让代理报告 `uname -a`、`pwd` 与 `nvidia-smi`。

添加WSL项目时，可在添加项目的文件选择器输入 `\\wsl$\`，选择Linux发行版和 `home/<user>/projects/humanoid-demo`。WSL代理优先搭配Linux文件系统；若使用Windows原生代理，官方建议项目保存在Windows盘并通过 `/mnt/<drive>/` 访问。

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

2026-10-28 已验证：WSL 主仓库在 `/home/lyrine/projects/humanoid-demo`，Windows 文件管理器地址为 `\\wsl.localhost\Ubuntu\home\lyrine\projects\humanoid-demo`；应用已登记该 Git 项目，原生 Bash 命令已在仓库目录运行。Windows 桌面的 `C:\Users\Oscar\Desktop\humanoid-demo-remote` 是另一处日志目录，不能作为主仓库。

Handoff 不限定 GitHub 服务。本机安装版应用要求两端 origin 都能解析出相同的主机／所有者／仓库，并使用相同仓库子目录。GitHub 网页登录、Codex GitHub 连接器和 Windows/WSL Git 命令认证分别生效；本机登录成功不能证明远端能访问私有仓库。先在执行端以不输出凭据的方式检查 `gh auth status`（若已安装）及 `GIT_TERMINAL_PROMPT=0 git ls-remote origin HEAD`。不要把访问令牌写入 URL、聊天或版本库，不覆盖远端未提交修改。

来源：[聊天跨主机交接](https://learn.chatgpt.com/docs/remote-connections#hand-off-a-chat-between-hosts)。匹配代码与失败证据：`runs/handoff-attempt-20261028/`。

## 同账号不等于同步所有本地内容

远程连接让你访问主机上的聊天和项目，不是把所有设备的磁盘、模型、环境和会话目录互相复制。代码用Git同步，运行结果保存到约定位置，现场资源由实际执行主机提供。

Windows原生应用通常使用 `%USERPROFILE%\.codex`，WSL CLI默认使用Linux家目录下的 `~/.codex`；两者默认不共享配置、认证缓存和历史。官方提供本机共享Codex home的方法，但本项目不需要先手工同步这些内部目录。不要把Mac、Windows和WSL的整个 `.codex` 目录当项目文件同步。

来源：[Windows与WSL的配置和会话](https://learn.chatgpt.com/docs/windows/windows-app#share-config-auth-and-sessions-with-wsl)。
