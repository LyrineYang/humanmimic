# HumanMimic 代码同步与Linux交接

更新于2026-11-02。当前工作顺序是读取最新状态、核对提交、迁移并验证目标环境，再按HANDOFF推进R4。早期Mac→Windows连接失败、“目录不存在”和初次部署记录已归入[历史文档索引](docs/archive/README.md)，不是当前部署结论。

## 当前可核实的边界

- 规范仓库：`LyrineYang/humanmimic`，稳定ID1436901913，仍为private；旧名`humanoid-demo`留在历史证据中。
- 原4060/WSL的R1/R2已完成工程验收；R3现场相机和R4另行验收，详见[PLAN](PLAN.md)、[HANDOFF](HANDOFF.md)。服务器有更晚记录时先核对，不按历史失败重做已完成工作。
- 用户提供服务器工作副本路径`/home/junqiy/projects/humanmimic`。本轮在该Linux/V100服务器整理代码；R4独立环境及运行证据见PLAN，Git版本与物理/研究验收分别报告。
- 后续以`main`为主线；旧`codex/linux-handoff`是当时交接快照，不要求始终与main相同。研究工作已整理为整合提交e4c50ac，并于2026-11-02按用户要求推送main；原tip及原本机文档由两个archive标签同步保留，不重写已发布历史、不强推。

## 已有副本同步到交接版本

在**待同步的那台机器**、正确工作副本中执行；先检查并保留本地修改。以下只更新代码，不是环境安装或运行路径迁移脚本：

```bash
pwd
git status --short
git remote set-url origin https://github.com/LyrineYang/humanmimic.git
git fetch origin
git merge --ff-only origin/main
git rev-parse HEAD
git rev-parse origin/main
git ls-remote origin refs/heads/main
```

本地HEAD、origin/main与远端main三个SHA相同，才说明同步完成；本地领先则可能仍有未推送提交。若快进失败、目录有未保存修改或出现本地独有提交，保留现场并检查差异，不使用`reset --hard`、`clean`或强推来制造一致。需要进一步合并时记录合并理由与检查结果。

新机器可从README的规范仓库克隆；只获取当前主线时：

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch main \
  https://github.com/LyrineYang/humanmimic.git
cd humanmimic
```

私有仓库认证使用用户已有通道；不把token、SSH配置或账号缓存放进项目。此命令跳过大LFS下载，不能据此认定模型、原始结果或环境已迁移。

## 仓库改名与运行路径分别处理

| 项目 | 本次处理 |
| --- | --- |
| GitHub origin、克隆命令、网站/文档仓库链接 | 使用`LyrineYang/humanmimic` |
| 源WSL目录`/home/lyrine/projects/humanoid-demo` | 现有实际目录，保持原状 |
| 原D盘根`/mnt/d/humanoid-demo-r2` | 原始资产/缓存/结果位置，保持原状 |
| 用户服务器目录`/home/junqiy/projects/humanmimic` | 已在目标机建立独立R4环境；完整R1/R2迁移仍待验收 |
| 历史runs、绝对symlink、冻结清单和SHA | 保留原字节/身份；通过新映射和新server运行记录接入 |

不要对整个仓库全局替换名称。Git同步不复制`.local/`、模型、完整视频、缓存和全部`runs/`；按[HANDOFF资产表](HANDOFF.md#52-git克隆不会带来的内容)通过授权私有通道迁移，保留原文件和失败。

## 执行前的接手顺序

读STARTUP_PROMPT→PLAN当前状态/验收→HANDOFF，核对目标机与活跃任务，再检查现有环境和结果。需要迁移的路径、SDK、boot保护和硬件身份单独形成server配置/版本；原冻结清单不是可任意改名的安装配置。所有新检查保存版本、输入SHA、日志、状态和录像，不能把缓存复演或旧主机通过当作服务器验收。

旧Codex跨设备界面操作仅作当时记录，见历史索引；本文件不把旧应用入口、连接失败或旧设备目录当当前接手前提。
