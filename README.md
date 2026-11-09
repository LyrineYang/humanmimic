> GitHub推送状态、本地接手、已保存演示和实验索引：[2026-11-09迁移入口](docs/migration-20261109/README.md)。

<p align="center">
  <img src="docs/assets/hero.svg" alt="HumanMimic — Video to humanoid motion. Run, inspect and extend a simulation pipeline." width="100%">
</p>

<p align="center">
  <a href="#getting-started">Get started</a> &nbsp; · &nbsp;
  <a href="docs/usage.md">Usage</a> &nbsp; · &nbsp;
  <a href="#how-it-works">Pipeline</a> &nbsp; · &nbsp;
  <a href="docs/insights.md">Insights</a> &nbsp; · &nbsp;
  <a href="docs/troubleshooting.md">Troubleshooting</a>
</p>

# HumanMimic

**Turn a human-motion video into a G1 simulation you can inspect.**

HumanMimic connects GEM-X motion estimation, a pretrained SONIC controller and MuJoCo. Give it a short video; the pipeline extracts human motion, runs the robot controller, and saves a side-by-side comparison with the intermediate data and execution metrics.

**Developer preview · Simulation only · Rebuildable Linux/V100 CUDA example.** Recorded-video and reference-motion workflows are implemented. Live-camera work is skipped for the current stage; video-based object reconstruction and dexterous interaction are the next research direction.

**R4 research in development:** Learn an initial manipulation from video, then use interaction evidence to revise the object model and spend observations where they matter for stable grasping and precise placement. LEAP sensing, CUDA shape/pose/compliance estimation and explicit memory have runnable components. Current 2 N grasp/place acceptance, the complete video-to-policy learning pipeline and manipulation gains remain unverified. Frozen ViViDex inference and paired contact correction now run locally; the 30-pair after-release accuracy gate failed ([current results](docs/results.md#vividex-contact-integration--november-9-2026)). Read the [experiment design (Chinese)](docs/r4-multimodal.zh-CN.md), [latest prerequisite results](docs/results.md#r4--november-3-prerequisite-results) or [video-learning alternatives and reproduction estimates (Chinese)](docs/research-video-interaction.zh-CN.md#11-视频学习操控的候选实现与复现难度2026-11-04).

## What you can do

- **Run a video through the full pipeline** — from the original frames to recorded robot execution.
- **Inspect what happened** — keep the motion estimates, controller references, actual states and timing in one run directory.
- **Work with cached stages** — reuse verified extraction data and preserve interrupted or failed attempts.
- **Evaluate and extend** — compare motion events and physical stability, then build on the same frozen controller.

<p align="center">
  <a href="docs/results.md"><img src="docs/assets/demo-frame.jpg" alt="Video input, estimated 2D keypoints, estimated 3D body and actual G1 simulation at the same source time." width="100%"></a>
</p>

*Example output: original video → 2D/3D estimate → recorded robot execution.* This is a static frame from a complete 31-second run. [Source / creator](https://www.youtube.com/watch?v=gRexOgq8h-8) · [Results and full-media locations](docs/results.md)

## Getting started

### 1. Get the source

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/LyrineYang/humanmimic.git
cd humanmimic
```

Already have a checkout? See the [repository synchronization guide](REMOTE_WORK.md) and verify the revision before resuming on another machine.

The current source includes a generated CUDA example with no MANO, private videos or trained weights. These commands are available on `main` from commit `e4c50ac`, containing `scripts/humanmimic.py`. The original R1/R2 results remain tied to the 4060 workstation.

### 2. Build and try the supported example

On Linux x86_64 with a V100 and a compatible existing NVIDIA driver:

```bash
python3 scripts/humanmimic.py doctor --target r4-v100
python3 scripts/humanmimic.py bootstrap \
  --prefix "$PWD/../humanmimic-data/r4/envs/r4-core" \
  --cache "$PWD/../humanmimic-data/r4/cache/bootstrap" \
  --output runs/install-r4-01
source scripts/activate-r4-research.sh
nvidia-smi --query-gpu=uuid,name,memory.free,utilization.gpu --format=csv
# Replace GPU-... with one available device UUID:
python scripts/humanmimic.py example \
  --gpu GPU-... --output runs/my-first-example
```

The installer verifies a pinned Conda base and hashed wheels. It needs about 20 GiB free disk; the bounded example requires one explicitly selected GPU and has no CPU fallback. [Setup, proxy/offline options and target configuration](docs/getting-started.md#prepare-a-runtime)

### 3. Read the result

Open `runs/my-first-example/REPORT.md`, `comparison.svg` and `result.json`. Generated observations, estimated shape/pose/compliance and evaluation data remain separate. This is an analytic reconstruction example, with **no physical manipulation**. Execution, task checks and research acceptance are separate fields; producing results does not prove useful grasping or calibrated uncertainty.

```bash
python3 scripts/humanmimic.py inspect runs/my-first-example
```

| Your next step | Where to go |
| --- | --- |
| Inspect results without a GPU | [Evidence and limitations](docs/results.md) |
| Use a real video | [R1/R2 setup and usage](docs/usage.md#video-to-simulation); full server migration remains unverified |
| Diagnose the server's R2 gaps | `python3 scripts/humanmimic.py doctor --target r4-v100 --stage r2` |
| Develop a change | [Contribution and regression commands](CONTRIBUTING.md#routine-checks) |
| Explore the research | [Memory, contact and geometry experiments](docs/r4-multimodal.zh-CN.md) |

The original WSL execution guard remains active. Read-only diagnostics report its restrictions instead of requiring a false boot identity or storage marker.

## What works today

| Workflow | Availability | Verified result |
| :--- | :--- | :--- |
| Reference-motion tracking | Implemented | Five fixed motions, two trials each: **10/10 passed** |
| Recorded-video imitation | Implemented; offline | Held-out videos: **4/5 passed**; debug videos: **3/5 passed** |
| Live-camera input | Skipped for this stage | Not accepted |
| Generated CUDA example | Rebuild and stable run/inspect commands | Independent environment and analytic first-run evidence; no robot execution |
| Video geometry → dexterous interaction | LEAP/CUDA sensing, estimation and memory components implemented | Targeted V100 checks passed; full video frontend, successful manipulation and geometry gains unverified |

The R1/R2 numbers are small engineering suites on the original 4060 environment; the R4 component checks use V100. All ten current video rollouts were stable; three still failed motion-event checks. Full videos remain local, and all five held-out videos have been used. [Complete results and limitations →](docs/results.md)

## How it works

![Video → GEM-X → SOMA/SMPL reference → frozen SONIC → G1 in MuJoCo, with actual-state feedback. The dashed scene-adaptation branch is proposed work.](docs/assets/pipeline.svg)

Perception runs offline in stages, then releases its models before the controller starts. SONIC turns the motion reference and robot-state history into joint targets; MuJoCo supplies the next physical state. The pipeline records what the robot actually did, alongside what it was asked to do.

[Architecture and source map →](docs/architecture.md)

## What we are learning

**A stable robot can still miss the gesture.** We keep event checks separate from physical stability, so a visually plausible rollout does not hide an imitation failure.

**Limited memory favors inspectable stages.** Separating extraction, control and rendering made the accepted offline workflow possible on an 8 GB GPU. The caches also make failures easier to locate and investigate.

The next question is whether task-relevant object geometry reconstructed from video can improve dexterous manipulation accuracy under a fixed observation and compute budget. The review separates reconstruction, contact estimation and physical execution, with independent geometry for evaluation. [Detailed research report (Chinese)](docs/research-video-interaction.zh-CN.md).

[Evidence-backed insights](docs/insights.md) · [Research questions and experimental design](docs/research.md)

## Documentation and contributing

| Need | Read |
| :--- | :--- |
| Prepare dependencies and assets | [Getting started](docs/getting-started.md) |
| Run a video or reference motion; inspect outputs | [Usage guide](docs/usage.md) |
| Understand a blocked run or an unexpected result | [Troubleshooting](docs/troubleshooting.md) |
| Find the code for a pipeline stage | [Architecture](docs/architecture.md) |
| Check successes, failures and evidence | [Results](docs/results.md) |
| Suggest a fix or explore an idea | [Contributing](CONTRIBUTING.md) |

Bug reports, clearer setup instructions and well-scoped experiments are useful contributions. Include your environment, command and relevant outcome so the work can be reproduced. Research ideas are welcome alongside practical improvements; [the contribution guide](CONTRIBUTING.md) explains how to separate a hypothesis from a demonstrated result.

<details>
<summary>Project operations and future website</summary>

- [Linux migration / R4 handoff](HANDOFF.md) — environment and asset transfer, in Chinese.
- [Current plan](PLAN.md) · [Experiment history](EXPERIMENTS.md) — authoritative research state and historical evidence, in Chinese.
- [Website design brief](docs/website.md) — local prototype and later hosting preparation.

</details>

## Acknowledgments and license

Built on [SONIC / GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl), [GEM-X](https://github.com/NVlabs/GEM-X), SOMA/SMPL representations and [MuJoCo](https://github.com/google-deepmind/mujoco). We reuse pretrained models; [UPSTREAM.json](UPSTREAM.json) records the integration boundary.

The repository is currently private and has no project-wide open-source license. Upstream code, models and videos retain their own terms. [Asset and attribution notes →](docs/getting-started.md#assets-and-attribution)
