# HumanMimic 本地接手与结果入口

技术路线、历次设计决策与失败分析见[技术迭代交接](../technical-iteration-handoff.zh-CN.md)。

**推送结果：已完成服务器现有可迁内容的GitHub上传。** `main`保存代码、配置和237项精选结果/演示；已有65个大文件附件（8,118,315,384字节，约8.12GB）全部上传同仓库草稿Release，对应13,292个源文件。没有新增打包或恢复复杂核验。源服务器原件保留；旧WSL数据等历史缺口单列，未声称整个历史项目已齐全。上传记录见[delivery-status.json](delivery-status.json)和[upload-only-report.json](upload-only-report.json)。

本次仅交接HumanMimic。代码、冻结协议、实验摘要及237项精选结果/原始演示已commit并push到main；大文件使用已经生成的同仓库Release附件。用户最新要求是不再创建归档、不继续复杂核验，完成推送和内容更新。下方校验命令仅供本地按需使用，不是本轮继续执行的任务。

## 本地先用起来

```bash
git clone https://github.com/LyrineYang/humanmimic.git
cd humanmimic
python3 -m http.server 8000 --bind 127.0.0.1
```

已有演示入口：

- [预训练Adroit糖盒搬移](../../runs/story-contact-20261109-01/vividex-relocate-final/episode-00.mp4)：原状态策略，非视频输入，3/3开发回合满足原3cm标准。
- [香蕉卸载释放](../../runs/story-contact-20261109-01/vividex-release-retrace/episode-00.mp4)：预训练放入加脚本张手/撤回，验证支撑、脱手和稳定；释放不是学习结果。
- [早期释放失败](../../runs/story-contact-20261109-01/vividex-release-01/episode-00.mp4)：保留失败及同目录结果，不只展示成功。
- [接触校正机制](../../runs/story-contact-20261109-01/demo-final/contact-corrected/execution.mp4)与[相同探触基线](../../runs/story-contact-20261109-01/demo-final/force-only/execution.mp4)：简化固定夹持、已知平面、单方向，不是完整灵巧手操作收益。
- [已有历史LEAP演示目录](../../runs/demo-showcase-20261109-01/index.html)：超过当前2N力界的旧开发参考。本次仅保存既有文件，没有生成新showcase或录像。

以上材料随普通clone可得，无需运行核验流程即可查看。可选的文件校验入口为`python3 scripts/verify-handoff-assets.py`。`published-files.csv`列出实际提交文件的大小与SHA-256。`selected-results.csv`是精选索引；完整源端索引见`artifact-index.csv.gz`，解压后可用表格软件筛选。索引中的路径相对于恢复根目录（含`humanmimic/`和相邻`humanmimic-data/`），不能把“索引有记录”理解为原始文件已进入Git。

## 当前结果与下一步

[30组冻结开发对照](../../runs/vividex-contact-integration-20261109-01/validation/result.json)：失败惩罚后的最终X边缘误差25.640→24.580mm，改善4.14%；完整条件16/30。执行完成，研究门槛failed。

[最后的释放/探触时机开发试跑](../../runs/vividex-release-timing-20261109-01/pilot04/result.json)：early误差11.788→9.673mm（17.94%），supported11.856→9.908mm（16.42%），每路5/6有效，均低于25%改善门槛。使用公共载荷转移、柔顺释放与PPO之后的自由腕工作空间修正；不是实体机械臂能力。8101–8103已经用于开发，8201–8206尚未使用。

本地可直接分析这些逐试次JSON和`measurements.csv`；全量NPZ状态、动作、模型、原始/处理后数据和所有失败保存在完整归档。先恢复状态并验收新录像脚本，再冻结控制器使用新种子比较同一次探触在不同阶段的效果。完整LEAP低力、SE3/顺应性校准、正式E3和视频前端仍未完成。

## 完整归档与私有下载

服务器交接目录为`/home/junqiy/projects/humanmimic-handoff-20261109/`，由四个源目录和相关外部日志/脚本盘点而来，未按`.gitignore`跳过实验内容。原项目工作树与实验进程保留。

仓库是公开的；完整原始归档使用同仓库的[草稿Release](https://github.com/LyrineYang/humanmimic/releases/tag/untagged-e93bcff1989da42021d9)作为私有交接位置，仅有写入权限的账号可见，匿名请求已验证404。标签为`humanmimic-handoff-20261109`。源端保存13,292个文件、15.33GB内容，压缩归档合计约8.12GB；65个传输分片均有SHA-256。最终上传状态以本目录的`delivery-status.json`为准；按用户最新要求，不继续全量远端回读和解包核验。附件内的早期状态文字保留为打包时快照，以main中的当前报告为准。

分片以128MiB为上限，支持片级续传：已经验证的片会跳过，中断片重新下载。下载已有大文件附件时，在本机登录有仓库push权限的GitHub账号并执行：

```bash
gh auth login
python3 scripts/download-handoff.py \
  --manifest docs/migration-20261109/TRANSFER.json \
  --output ../humanmimic-transfer
gh release download humanmimic-handoff-20261109 -R LyrineYang/humanmimic \
  --pattern SHA256SUMS --pattern archive-manifest.csv \
  --pattern handoff-status.json --pattern metadata-file-manifest.csv \
  --dir ../humanmimic-transfer --clobber
cd ../humanmimic-transfer
tar -xzf handoff-metadata.tar.gz
python3 verify_handoff.py --root .
mkdir -p restored
for volume in archives/humanmimic/*.tar.gz; do tar -xzf "$volume" -C restored; done
python3 verify_handoff.py --root restored --restored
```

下载脚本验证GitHub存储摘要、每片下载内容和重组归档的SHA；整卷tar各自独立，不能跨卷cat拼接。Linux也可`sha256sum -c SHA256SUMS`，macOS用`shasum -a 256 -c SHA256SUMS`。仓库设置了结果文件`-text`属性以保持不同操作系统下字节一致。

日常开发用Git最新源码；全量归档是服务器发布前快照，并附发布后source bundle，不要覆盖新克隆中已更新的文档。按归档README将`humanmimic-data/`置于源码旁，并恢复上游Git bundle；分析原始记录则用解包的`runs/`。排除、历史缺口和补取方式见[缺失清单](missing-and-recovery.csv)。服务器原件与已有附件保留。GitHub自动生成的Source code ZIP仅含Git文件，不含完整原始归档。

## 环境和缺口

仅浏览CSV/JSON/MP4无需GPU。完整运行采用隔离的Linux x86_64/NVIDIA环境：R4为Python3.10.14、Torch2.5.1+cu118、MuJoCo3.2.7；ViViDex单独使用MuJoCo2.3.7、dm-control1.0.14。锁、启动脚本、实测freeze及R4 wheelhouse归档均保留；不复制Conda前缀冒充跨平台环境。

R1/R2原WSL完整输出、R2完整视频和未提供路径的MANO资产仍缺失，仅有历史引用；受限资产须按许可本地恢复。密钥、令牌和账号配置不公开、不进入归档。最新release-timing的状态已保存，原始录像尚未生成。恢复后仍需新机GPU验收，迁移期间没有启动训练或新实验。
