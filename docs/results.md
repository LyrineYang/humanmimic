# Results, including the failures

[Home](../README.md) / Evidence

**Updated: November 9, 2026.** R1/R2 below preserve engineering acceptance from the original RTX 4060 Laptop environment. R4 component evidence comes from the V100 server. R1 uses fixed official/debug examples; R2 uses five debug and five held-out videos with narrow input conditions. Neither is a broad generalization benchmark. The earlier [demo bundle](#demo-showcase--november-9-2026) presents historical recordings. New pretrained and controlled-contact results are reported [below](#contact-memory-story--november-9-2026). Latest clarification: raw experiment demos are allowed; showcase compilation is disabled. Native ViViDex contact-correction validation now saves states, actions and metrics by default.

## R1 — Reference tracking

**10/10 trials passed; all five motions passed twice.** All 6,300 control samples are retained. Per-trial joint RMSE spans **0.10875–0.17517 rad**, below the predeclared 0.35 rad gate. Gravity, contact and a free root remain enabled; actual state is not overwritten with reference poses.

| Motion | Trial 1 RMSE (rad) | Trial 2 RMSE (rad) | Outcome |
| :--- | ---: | ---: | :--- |
| Macarena | 0.13378 | 0.13409 | 2/2 passed |
| Dance in da party | 0.17270 | 0.17517 | 2/2 passed |
| Squat | 0.13419 | 0.13121 | 2/2 passed |
| Walking quip 360 | 0.10918 | 0.10875 | 2/2 passed |
| Forward lunge (mirrored reference) | 0.13415 | 0.13574 | 2/2 passed |

[Accepted R1 evidence and artifact hashes](../evidence/r1-acceptance-20261029.json) · [Frozen motion list](../configs/r1-suite.json)

The initial 3/10 failed batch and an interrupted batch remain in the history and are excluded from the accepted batch. The accepted trials share one frozen runtime identity; results from different driver versions were not pooled. [What changed and what can be inferred](insights.md#02--the-clock-belongs-in-the-control-experiment)

## R2 — Recorded-video imitation

**4/5 held-out videos passed**, meeting the original at-least-4/5 gate. Debug results are **3/5 passed**. All ten current rollouts completed their physical path stably, consuming **12,095 source references** in total. Physical stability does not imply correct imitation: three videos still failed event checks.

| Split | Source | Action class | Motion events | Physical execution | Full outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| debug | [QqvZAUEOrAQ](https://www.youtube.com/watch?v=QqvZAUEOrAQ) | dance | 6/6 | passed | **passed** |
| debug | [0EpP3pYUYTk](https://www.youtube.com/watch?v=0EpP3pYUYTk) | lower body | 7/7 | passed | **passed** |
| debug | [vTx_ldn6MCA](https://www.youtube.com/watch?v=vTx_ldn6MCA) | upper body | 3/4 | passed | **failed** |
| debug | [6uqztDO_7kQ](https://www.youtube.com/watch?v=6uqztDO_7kQ) | stepping | 0/6 | passed | **failed** |
| debug | [2e_7XBmpw14](https://www.youtube.com/watch?v=2e_7XBmpw14) | dance | 5/5 | passed | **passed** |
| heldout | [ROZy7jawHf4](https://www.youtube.com/watch?v=ROZy7jawHf4) | trunk | 8/8 | passed | **passed** |
| heldout | [U7Nrwyu6Uqo](https://www.youtube.com/watch?v=U7Nrwyu6Uqo) | lower body | 6/6 | passed | **passed** |
| heldout | [gRexOgq8h-8](https://www.youtube.com/watch?v=gRexOgq8h-8) | dance | 6/6 | passed | **passed** |
| heldout | [dIfUVvoVXRM](https://www.youtube.com/watch?v=dIfUVvoVXRM) | dance | 5/5 | passed | **passed** |
| heldout | [GP4YqDYMmcI](https://www.youtube.com/watch?v=GP4YqDYMmcI) | dance | 5/6 | passed | **failed** |

[Accepted R2 evidence and artifact hashes](../evidence/r2-acceptance-20261101.json) · [Frozen source/event manifest](../configs/r2-suite-frozen-20261101.json)

All 50 output MP4 files were fully decoded and bound to artifact hashes in the acceptance review. This is a media-integrity result, not 50 independent trials. The five held-out sources have all been used. Three held-out dance sources share a creator, so the split has correlated content and limited diversity. New tuning requires a new predeclared test split.

### Failures remain part of the result

- **Arm circles (debug): 3/4 events.** The final right-arm lowering did not reach the fixed amplitude criterion.
- **Stepping (debug): 0/6 events.** The final initialized rollout was stable but did not satisfy the frozen stepping-event checks. Its earlier 22/574-reference fall remains a separate failed attempt.
- **Dance GP4YqDYMmcI (held-out): 5/6 events.** The wide-crouch left-knee threshold was 0.7 rad; the estimate reached about 0.48139 rad and the robot 0.41443 rad. The deficit was already present in the reference. Its cause has not been independently isolated; thresholds and side labels were not changed after testing.

## How to read the demonstration

![Three points from a complete held-out comparison: original video, estimated 2D keypoints, estimated 3D body, and recorded physical execution.](../evidence/r2-kpop-demo-preview-20261101.jpg)

The preview samples the beginning, middle and end of the complete 31-second source [gRexOgq8h-8](https://www.youtube.com/watch?v=gRexOgq8h-8). Original footage belongs to its creator. The robot image is rendered from recorded actual states after physical execution; it is not a reference-pose animation. Estimated 3D body positions are not human ground truth. The comparison preserves visible pose and phase differences.

The homepage's [single-frame image](assets/demo-frame.jpg) is extracted at comparison time 15.56 seconds from the same full MP4. It is a static preview, not a new experiment. [Preview provenance](assets/provenance.json)

## Full media on the execution machine

Raw reports, inputs and full videos are intentionally not tracked in Git. The paths below are **local artifact locations**, not downloadable GitHub links. Each hash is recorded in the tracked acceptance JSON above.

R1 suite root: `runs/r1-suite-acceptance-20261029-03/`. Each trial directory contains `REPORT.md`, `actual-state.npz`, native controller logs and `actual-execution.mp4`.

R2 suite report: `runs/r2-suite-acceptance-20261101-01/REPORT.md` (the local link resolves into the D-drive storage root). Per-source directories under `/mnt/d/humanoid-demo-r2/runs/`:

| Source | Run directory | Comparison |
| :--- | :--- | :--- |
| QqvZAUEOrAQ | `r2-debug-init-QqvZAUEOrAQ-20261101-01` | `demo/comparison.mp4` |
| 0EpP3pYUYTk | `r2-debug-init-0EpP3pYUYTk-20261101-01` | `demo/comparison.mp4` |
| vTx_ldn6MCA | `r2-debug-init-vTx_ldn6MCA-20261101-01` | `demo/comparison.mp4` |
| 6uqztDO_7kQ | `r2-debug-init-6uqztDO_7kQ-20261101-01` | `demo/comparison.mp4` |
| 2e_7XBmpw14 | `r2-debug-init-2e_7XBmpw14-20261101-01` | `demo/comparison.mp4` |
| ROZy7jawHf4 | `r2-heldout-ROZy7jawHf4-20261101-01` | `demo/comparison.mp4` |
| U7Nrwyu6Uqo | `r2-heldout-U7Nrwyu6Uqo-20261101-01` | `demo/comparison.mp4` |
| gRexOgq8h-8 | `r2-heldout-gRexOgq8h-8-20261101-01` | `demo/comparison.mp4` |
| dIfUVvoVXRM | `r2-heldout-dIfUVvoVXRM-20261101-01` | `demo/comparison.mp4` |
| GP4YqDYMmcI | `r2-heldout-GP4YqDYMmcI-20261101-01` | `demo/comparison.mp4` |

Each R2 package also retains source, extraction and robot panels; source hashes and timestamps; GEM-X/SOMA outputs; converted references; actual states; body/event evaluation; timing and visual audits. Consult the tracked acceptance JSON for exact original and supplementary audit paths, including failures.

## Acceptance boundaries

| Evidence layer | Status |
| :--- | :--- |
| Source/environment checks on the accepted workstation | `passed` |
| R1/R2 headless closed-loop simulation | `passed` within the stated suite gates |
| Recorded actual-state offline playback | `passed` |
| GPU-accelerated graphical window | `awaiting_verification` |
| R3 on-site camera, freshness, recovery and latency | Skipped for this stage; historically unverified |
| R4 sensing, CUDA joint estimation, memory/control | Implemented; targeted V100 engineering checks passed |
| R4 successful manipulation and local-geometry gains | `awaiting_verification`; complete video frontend and experimental comparison remain open |
| Independent R4 Linux/V100 rebuild | Passed: clean committed checkout, hashed empty-prefix installation, CUDA first run and runtime regressions; see [delivery evidence](../evidence/runtime-portability-20261102.json) |

The completed experiments used no newly billed cloud resources; that does not make local computation free. No real robot or new training is included. The R4 runtime is independently prepared on the server; R1/R2 full pipeline migration is not established by it. [Current plan](../PLAN.md) remains the execution authority.

The 2026-11-01 server inventory and research review are preparation evidence, not new robot results. See [server readiness](server-readiness.zh-CN.md) and [research](research.md); the accepted execution results above remain from the original workstation.

## R4 — generated example and current component evidence

The stable [setup](getting-started.md#prepare-a-runtime) and [example](usage.md#cuda-example-and-results) paths build a separate Linux/V100 prefix and generate observations without private assets. A completed example produces a coarse/estimated surface illustration, estimated state/covariance and independent analytic metrics. `execution_status`, `task_status` and `acceptance_status` are separate; an exit-0 run is not a successful grasp claim.

The November 2 research review fixes exclude internal union faces from geometry metrics, remove continuous-force information from the binary baseline, and freeze independent per-frame poses for shape-only evaluation. [Review evidence](../evidence/r4-review-fixes-20261102.json) records 15 targeted, 15 P2 and 18 memory/control checks. [Earlier online evidence](../evidence/r4-memory-control-20261102.json) records an actual LEAP negative control: execution completed, task failed as expected. Neither establishes a geometry-induced operation gain; the later calibration below has a narrower, explicitly stated scope.

The [runtime-portability delivery](../evidence/runtime-portability-20261102.json) records the independent rebuild from 57 hashed wheels, eight environment/CLI checks, six installer contracts, targeted 15/15 and P2 15/15 CUDA regressions, and a fresh six-check LEAP force-bridge run with NVIDIA EGL. The generated example has translation RMSE 0.0194 mm, surface RMSE 0.0260 mm and compliance error 0.0555 mm/N on its analytic fixture. Its pose interval does not cover the fixture error; these numbers do not establish calibrated uncertainty or operation accuracy. Ordinary inspection returns 0 and strict acceptance inspection returns 3 for the same saved result.

Historical metrics above are not replaced by new environment runs. Raw installation, example, force-calibration video and audit outputs live in `runs/runtime-portability-20261102-01/`; [PLAN](../PLAN.md) is the current authority. Website links and HTML structure were checked; browser rendering and remote publication were not performed in this delivery.

## R4 — November 3 prerequisite results

The [prerequisite summary](../evidence/r4-prerequisites-20261103.json) records the latest frozen V100 evidence. Numerical estimation and hand kinematics use CUDA; MuJoCo dynamics run on the CPU and rendering uses NVIDIA EGL. These are simulation results, with no real-robot or live-camera acceptance.

| Evidence | Result | Limit |
| --- | --- | --- |
| LEAP force bridge / P2 joint estimator / memory, control and probes | `passed`: 6 / 15 / 31 CUDA checks | Module behavior, not successful manipulation |
| Full-hand loading at the calibration posture | `passed`: 20 fit + 20 separate verification trials; conservative local compliance bound about 0.1214 mm/N | Hand/probe response, not object material or arbitrary grasp posture |
| Conditional translation confidence | `passed`: 18/20 independent verification trials covered, after 20 fit trials; frozen interval multiplier 60.4293 | Two development objects and a fixed time window; multiplier is offline only, not applied to online covariance |
| Analytic joint confidence fixture | `passed`: 20/20 simultaneous final-frame xyz/scalar-compliance coverage | No rotation and no physical LEAP object-compliance validation |
| Earlier U-shaped object reference | T1 held 7.48 s; T2 errors 3.763 mm / 1.944 degrees | Exceeds the current 2 N force bound and predates controller changes; not an eligible E3 reference |
| Current bounded grasp/place reference | `failed` / `awaiting_verification` | No accepted T1/T2 under the current force bound; no demonstrated geometry or active-probing gain |
| Current online negative control | Execution `passed`, task `failed`; 4 s and 101 recorded frames | Confirms the isolated observation-to-estimator-to-control path only |

All three prerequisite cohorts have finished. Total charged occupancy is 3.0270 GPU-hours, with no billed cloud spend or learned-policy training. The overnight cohort has 139 commands and retains an overall `failed` status because four grasp candidates were rejected for missing the required two-finger load. These rejections are not erased by the calibration passes. E3 remains gated on accepted manipulation references and complete calibration; 24 held-out objects remain unused.

Raw outputs, private evaluation, videos and failure logs are retained in `runs/r4-prerequisites-live-20261103-01/` and `runs/r4-prerequisites-overnight-20261103-02/`; large media are not included in Git. The [video-learning comparison](research-video-interaction.zh-CN.md#11-视频学习操控的候选实现与复现难度2026-11-04) is a source review, not an additional runtime result.

## Demo showcase — November 9, 2026

**Ready locally:** [34.56-second showcase MP4](../runs/demo-showcase-20261109-01/media/showcase.mp4), [offline gallery](../runs/demo-showcase-20261109-01/index.html), [portable ZIP](../runs/demo-showcase-20261109-01/HumanMimic-demo.zip). These are execution-machine files, not GitHub download links. The ZIP is about 3.05 MiB and includes standalone videos, original recordings, still previews and provenance. Extract it and open index.html, or open the MP4 directly.

| Demo | Available presentation | What it establishes |
| --- | --- | --- |
| LEAP grasp, move, rotate and release | Full 12.04 s recording with result panel and logged height | Historical debug reference: 3.763 mm / 1.944 degrees, force exceeds current 2 N bound; no video-policy or E3 claim |
| LEAP lift and hold | Full 12.04 s recording | Historical 7.48 s hold, 0.949 mm penetration; same force/version limitation |
| Full-hand loading | Full 2.44 s calibration recording | Local posture loading, 20 fit / 20 verification trials; not arbitrary posture or object material |
| Four-finger force bridge | Full 2.04 s recording | Four distal assemblies and six component checks; not a whole-hand manipulation task |
| Video to G1 imitation | Existing comparison still | Original 4060 evidence; full 31 s comparison remains on the original machine |
| Coarse geometry to estimated geometry | Existing analytic SVG | Synthetic CUDA estimator output; no physical manipulation or real-video accuracy claim |

The presentation keeps every frame of each selected clip at 1× playback and applies only full-frame scaling, gamma/brightness adjustment and separate text panels. Grasp/place and hold video hashes match their original evaluations. Time/height labels come from the recorded CSV and do not feed any controller. These are selected demonstrations, not a sampled success-rate evaluation. All output MP4s were fully decoded; representative frames and a storyboard were visually inspected. Browser interaction with the HTML gallery remains unverified. Raw audit and local-media inventory are in runs/demo-showcase-20261109-01/; no failures were deleted.

To rebuild from the existing recordings, use a fresh output directory:

    source scripts/activate-r4-research.sh
    python -B scripts/package-r4-demo.py --output runs/demo-showcase-new

This packaging command uses the existing imageio_ffmpeg binary and installed Chinese fonts. It encodes media without starting CUDA estimation, dynamics, a learned policy or training. It does not require or renew the expired research campaign.

### Fast-demo plan and research continuation

The research question stays: **Can interaction revise an uncertain object model, and can task-directed observations turn that revision into more stable grasps and more accurate placements?** Current demo quality and scientific acceptance are tracked separately.

| Priority | Concrete next deliverable | Planning estimate and boundary |
| --- | --- | --- |
| Immediate | Use the packaged R4 footage; recover the full R2 comparison from /mnt/d/humanoid-demo-r2/runs/r2-heldout-gRexOgq8h-8-20261101-01/demo/comparison.mp4 | Packaging is complete; R2 transfer depends on original-machine access, no retraining |
| Presentation improvement | Reference/actual overlays, tactile heatmaps from recorded sensors, clearer lighting and camera framing | A few hours of preparation if source logs/rendering are available; label any recorded-state rerender, diagrams or illustrative animation |
| One pretrained manipulation skill | Check DexTrack's LEAP tracking branch or ViViDex's pretrained relocation example in an isolated environment | First-demo target 1–3 working days if assets/dependencies work; reserve an initial 2–8 GPU-hour proposal, not a completion guarantee or new authorization |
| Research acceptance | Accepted 2 N grasp/place reference, full state/compliance calibration, then fixed-controller E2 and same-budget E3 | Continue the existing gates; the demonstration selection does not relax thresholds or establish method gains |

Useful shortcuts include one fixed object/camera, an explicitly known mesh, offline reference calibration and a pretrained controller. They can produce a coherent demonstration before arbitrary-video reconstruction is ready. Keep these assumptions in the presentation, and report the reproduced method/hand separately from HumanMimic's online-refinement contribution. Do not turn a chosen successful seed into a generalization claim.

On November 9, the official [DexTrack README](https://github.com/Meowuu7/DexTrack) still provided pretrained tracking examples and LEAP/Franka support while withholding parts of its iterative training procedure; [ViViDex's MuJoCo README](https://github.com/zerchen/vividex_mujoco) still provided pretrained checkpoint links and relocation/pouring/placing training entry points. Neither was run here. The original continuous research window expired on November 5 at 08:54:06 Asia/Shanghai; a new bounded GPU execution window must be explicit before running new reproductions. This delivery adds zero research GPU-hours and no cloud charges.


## Contact memory story — November 9, 2026

**前轮保存快照：保存研究成果和已有demo，继续保存可展示的数据。最新视频权限与原生接入见下方追加结果。** 已停止展示加工，所有先前视频原样保留。运行入口默认无渲染，保存实际状态/动作而非先生成视频。小型可同步摘要见[证据文件](../evidence/story-contact-20261109.json)，详细story见[多模态方案第13节](r4-multimodal.zh-CN.md#13-故事优先的小切口手到了物体为什么还没放准2026-11-09)。

主线：**动作可以模仿，精度需要记住。** 稳定夹持后，手的位置不等于物体边缘的位置。一次对已知平面的轻触测到有效边缘偏差；同一控制器在后续目标处补偿这个偏差。该切片不需要从零训练或先恢复完整物体几何。

| 能力 / 证据 | 结果 | 不能据此推出什么 |
| --- | --- | --- |
| DexTrack LEAP资产检查 | 官方README列出权重；本机访问官方OneDrive返回403，按用户指示切换 | 不能断言作者未发布权重 |
| ViViDex公开sugar-box状态策略 | 3/3开发回合通过上游3cm终点条件；误差5.44/5.62/8.14mm | 不是视觉BC、不是从新视频学习，不是LEAP |
| ViViDex放入 + 脚本松手撤回 | 新开发种子5401–5403，3/3通过手脱离/杯体支撑/末段稳定检查；末.5秒漂移0.138/0.182/0.202mm | 松手是脚本，完整容积包容率未评估；目标点距离不等于容器任务成功率 |
| 接触校正独立测试台 | 6个冻结开发条件，A/B平均边缘误差8.667→0.068mm，最大修正误差0.166mm；探触峰值1.061N | 固定夹持约束、已知平面、简化夹持器、单方向；尚未接入ViViDex/LEAP，不是完整E3 |
| 接触记忆接口 | 无力接触拒绝、错误方向拒绝、旧夹持ID拒绝、重复事件不再缩小方差，共4项CUDA检查 | 无完整6D/形状/顺应性标定或滑移检测证明 |

接触对照不是“有力反馈”对“没有力反馈”：两组执行相同探触并退让，逐行核对7组（6验证+1演示开发点）的探触观测完全一致。A继续用粗模型，B只增加接触偏差读出和后续终点修正。原始单例8.00→0.055mm。验证条件分别为(夹持偏移mm,半宽误差mm)：(-10,0)、(-5,2)、(3,0)、(6,3)、(10,1)、(12,4)；全部保留。它们现已使用，不能继续称未见测试；项目24个保留对象未动。模型未用真实物体偏移/尺寸，真值只用于评价。

三种结果分别保存，不拼成已接通系统：预训练状态策略提供动作；脚本完成有限释放展示；接触估计证明一个受控机制。正式下一步是在相同观测/固定控制器下接通这个残差接口，避免预训练状态策略读取真值时掩盖待估量。

| 本机素材 / 记录 | 位置与说明 |
| --- | --- |
| 冻结条件与全部接触指标 | `runs/story-contact-20261109-01/verification-manifest.json`、`verification-summary.json`、`paired-probe-check.json` |
| 可恢复的接触对照 | `runs/story-contact-20261109-01/contact-state-archive/`：三组XML、NPZ实际qpos/qvel/ctrl/time、公开观测与私有评价CSV |
| 可恢复的预训练抓放 | `runs/story-contact-20261109-01/vividex-state-archive/`：三个MJB模型及NPZ实际状态/控制量，配套CSV、配置、权重/源码哈希 |
| 已有原始demo | `runs/story-contact-20261109-01/demo-final/`、`vividex-relocate-final/`、`vividex-place-02/`、`vividex-release-retrace/` |
| 用户停止前已有展示包 | `runs/story-contact-20261109-01/presentation/`；只保留，不继续编码或展示 |
| 失败与修复 | 各`*-session/job-0.log`和原始run均保留：旧SB3 API、place观测维度、释放仍接触、竖直关节余量不足；不从统计中抹去 |

归档复跑使用同一批已用种子，结果与录制时一致，不增加研究样本数。MJB需对应MuJoCo2.3.7读取；接触场景使用R4 MuJoCo3.2.7。模型恢复检查不渲染、不生成动画或视频，不能将它称作已观看的动画回放。最新成本、检查和文件完整性见同目录`preservation-check.json`及唯一GPU ledger。


## ViViDex contact integration — November 9, 2026

**接入与归档检查passed；最终放置收益验收failed。** 已把接触偏差记忆接入固定ViViDex sugar-box状态策略之后的原生Adroit放置控制。两个分支共享预训练输入动作、公共腕部/释放适配、一次探触、名义位姿先验，以及完全相同的物理起点。唯一对照差别为是否把接触偏差用于腕部X残差。物体自由运动，无固定夹持约束；姿态先验仍是两组共享的特权状态，实际尺寸未输入估计器，不是视觉策略。

[冻结协议](../configs/vividex-contact-pair-validation.json)共30对：6个新开发种子×5档局部半宽误差（−8/−4/0/+4/+8mm），验证后不调参。这些条件现已使用，原项目24保留对象未用。全部失败保留。

| 指标 | 基线 | 接触校正 | 解读 |
| --- | ---: | ---: | --- |
| 主指标：最终X边缘MAE，失败惩罚max(50mm,实际误差) | 25.640mm | 24.580mm | 改善4.14%，未达25% |
| 满足完整单试次条件 | 16/30 | 16/30 | 53.3%，未达80%，没有提高有效率 |
| 松手前X边缘MAE，全部30对 | 2.826mm | 1.059mm | 仅机制诊断，不能替代最终指标 |
| 最终X边缘MAE，不加失败惩罚 | 12.719mm | 9.551mm | 包括倾倒结果，不用于主结论 |
| 两组都合格的16对最终X边缘MAE | 3.576mm | 2.271mm | 条件子集，不能排除其余14对后宣称整体收益 |
| 最终Y位移误差，全部30对 | 31.057mm | 31.075mm | 当前只校正X，不能声称全平面放准 |

主指标平均改善1.060mm，按种子为簇的bootstrap95%区间为[0.0366,2.3192]mm；只有6个种子簇，结论限于这批开发条件。尽管存在小幅正向信号，≥25%改善/≥80%有效率两项预设门槛均失败。5组探触不合格，最大三轴探触力6.879N，超力证据未用于控制；10组最终姿态超10°，原因有重叠。所有终态均已脱手、得到桌面支撑且漂移≤2mm，仍将倾倒和探触失败计为失败。2N只是探针条件，整手力界没有通过。

工程交付：固定checkpoint CUDA推理；单方向CUDA记忆；公共同步探触与状态分支；编码器腕部稳定、两次共享位姿竖直对齐、被动卸载撤手；公共传感与私有评价分文件。MuJoCo使用上游原生动力学，策略/估计/统计为CUDA；没有CPU数值替代、训练或新依赖安装。校准探针和桌面使用明确碰撞参数，两组相同，保留原生手-物接触。此释放脚本是工程适配，不能归为ViViDex学习到的能力。

原始记录位于`runs/vividex-contact-integration-20261109-01/`：

- `validation/result.json`和`archive-verification.json`：全30对、按尺寸分组指标、失败与独立重算；源码入口[配对运行器](../scripts/run-vividex-contact-pair-gpu.py)、[GPU核验器](../scripts/check-vividex-contact-pair-gpu.py)。
- 每组`model.mjb`、`common-states.npz`、`fork-state.npz`、两组`*-states.npz`、`policy-input-actions.npz`：实际状态、控制、时间、测量量具状态与策略输入动作；`*-public.csv`和`*-private.csv`隔离。
- `shared-prior.json`、`shared-alignment.json`、`contact-memory.json`保存公共观测来源、接触事件和偏差更新；`frozen-source/`保存最终冻结源码；8版开发试跑、失败日志和静态诊断帧都保留。
- [可同步证据摘要](../evidence/vividex-contact-integration-20261109.json)记录状态、成本和能力边界。30对同起点及60分支恢复、有限性、无刚性耦合和最终误差重算均passed；不是动画播放验收。

本轮新增0.228643GPUh；新8GPUh台账累计0.346361，剩余7.653639，全部作业结束。原144GPUh台账未变，无付费或训练。沿用独立ViViDex环境，依赖检查通过；源码解析与无界面GPU/物理检查单列，未做动画回放或现场相机。本轮无新视频。用户允许原始实验demo，showcase仍禁止，两个打包器的拒绝检查通过。

下一步聚焦**稳定握持和从手到桌面的载荷转移**：用公共信号判断接触记忆何时仍有效，在新种子上比较同一次探触放在支撑前后的效果，再检查释放导致的偏差。当前证据支持“握持时局部校正有作用，释放过程会改变结果”，尚不支持完整操作收益或正式E3通过。
