<p align="center">
  <img src="docs/assets/hero.svg" alt="HumanMimic — From human motion to physical behavior. Video imitation and scene adaptation in simulation." width="100%">
</p>

<p align="center">
  <a href="#see-the-system">Demo</a> &nbsp; / &nbsp;
  <a href="docs/architecture.md">How it works</a> &nbsp; / &nbsp;
  <a href="docs/results.md">Results</a> &nbsp; / &nbsp;
  <a href="docs/insights.md">Insights</a> &nbsp; / &nbsp;
  <a href="docs/research.md">Research direction</a> &nbsp; / &nbsp;
  <a href="docs/getting-started.md">Get started</a>
</p>

# HumanMimic

**Turn observed human motion into measured humanoid behavior.**

HumanMimic is a simulation research project for video-driven humanoid imitation under a limited compute budget. It connects **GEM-X** motion estimation to a frozen, pretrained **SONIC** controller and a **Unitree G1** in **MuJoCo**. Every demonstration is paired with recorded physical states, timing checks and explicit acceptance criteria.

The next research question: **how much physical verification does a robot need to adapt a demonstration to its surroundings?**

| Reference motion · R1 | Video imitation · R2 | Verified platform |
| :--- | :--- | :--- |
| **10 / 10** trials passed | **4 / 5** held-out videos passed | **RTX 4060 Laptop · 8 GB** |
| Five fixed motions, two trials each | Five additional debug videos: 3 passed, 2 failed | Offline extraction, then closed-loop simulation |

<sub>Engineering acceptance, as of November 1, 2026. R1 uses fixed reference examples; R2 is a small, constrained video suite. These are not generalization benchmarks. Live-camera operation and scene adaptation remain unverified.</sub>

## See the system

<a href="docs/results.md">
  <img src="docs/assets/demo-frame.jpg" alt="A frame from one held-out K-pop sequence: original video, estimated 2D keypoints, estimated 3D body and recorded robot execution." width="100%">
</a>

**One source. A traceable path to execution.** The static preview is taken at 15.56 seconds from a complete 31-second held-out sequence. The robot panel is an offline rendering of **recorded MuJoCo states** from a real controller rollout. Body estimates are not 3D ground truth; visible differences in pose and phase remain in the comparison.

[Source video / creator attribution](https://www.youtube.com/watch?v=gRexOgq8h-8) · [All ten results and media locations](docs/results.md) · [Machine-readable evidence](evidence/r2-acceptance-20261101.json)

Full videos and model assets stay on the execution machine. The repository includes this small preview and audited summaries; cloning it does not download the full demonstrations.

## From pixels to physics

![Pipeline: video to GEM-X, SOMA/SMPL reference, frozen SONIC and G1 in MuJoCo, with actual-state feedback and a separate proposed scene-adaptation branch.](docs/assets/pipeline.svg)

1. **Observe.** Normalize the complete source timeline and estimate human motion with GEM-X.
2. **Translate.** Convert SOMA geometry into SONIC's SMPL reference convention, preserving frame identity and timing.
3. **Execute.** Stream cached references to the frozen controller. Joint targets drive PD control and physical simulation; actual state returns to the controller.
4. **Measure.** Compare consumed references with recorded execution, audit motion events, and retain complete successes and failures.

[Architecture and code map →](docs/architecture.md)

## What the experiments taught us

**Stability and imitation are different outcomes.** All ten current R2 rollouts were physically stable, while only seven passed the complete event checks. A robot can stay upright and still miss the demonstrated action.

**Time is part of the experiment.** R1's initial batch passed 3/10 trials. After correcting simulation pacing and running a new, internally consistent batch, 10/10 passed. The old failures remain in the record; the batches also used different driver versions, so this is not a clean single-variable ablation.

**Small hardware changes the workflow.** Sequential extraction, cache persistence and separate controller execution made the accepted offline pipeline possible on an 8 GB GPU. This does not establish real-time perception.

[Read the evidence-backed insights →](docs/insights.md)

## Research direction

We are investigating **scene-constrained reference adaptation with a fixed controller**: propose a small change to a demonstrated reach, reject geometrically invalid candidates, and spend a limited number of closed-loop simulations on the remaining candidates.

The initial setting is deliberately narrow: mostly fixed feet, one arm, one static box, known geometry. The intended contribution is an evaluated allocation of verification effort under a fixed budget. **This module is not implemented or validated yet.**

[Hypotheses, baselines and decisive experiments →](docs/research.md)

## Project status

| Stage | Scope | Acceptance |
| :--- | :--- | :--- |
| **R1 · Reference tracking** | Fixed G1 motions through SONIC + MuJoCo | `passed` — 10/10 trials, 5/5 motions twice |
| **R2 · Recorded video** | Video → GEM-X → SOMA/SMPL → physical execution | `passed` — 4/5 held-out; one failed event retained |
| **R3 · Live camera** | Streaming perception, recovery and latency | `needs_input` — no on-site camera acceptance |
| **R4 · Scene adaptation** | Constrained reference edits + closed-loop selection | `awaiting_verification` — not implemented |

The five R2 held-out videos have all been used. Future tuning requires a new, predeclared test split. GPU-accelerated window rendering is also unverified; current evidence includes headless control and software-rendered actual-state playback.

## Explore and reproduce

Start with the [getting-started guide](docs/getting-started.md). The repository contains source, pinned dependencies, configuration and compact evidence. Environments, pretrained weights, licensed body assets and raw run packages are prepared separately. Fresh-machine installation has not been accepted yet.

```bash
# Inspect the source without automatically downloading large LFS assets.
GIT_LFS_SKIP_SMUDGE=1 git clone --recurse-submodules https://github.com/LyrineYang/humanoid-demo.git
cd humanoid-demo
```

| Read | Purpose |
| :--- | :--- |
| [Getting started](docs/getting-started.md) | Verified environment, assets and execution entry points |
| [Linux / R4 handoff (Chinese)](HANDOFF.md) | Context, assets, server compatibility, migration checks and the R4 execution plan |
| [Architecture](docs/architecture.md) | Data flow, controller feedback and source map |
| [Results](docs/results.md) | Complete R1/R2 outcomes, failures and local media index |
| [Insights](docs/insights.md) | Observations, interpretations and their limits |
| [Research design](docs/research.md) | R4 hypotheses, comparisons and acceptance |
| [Website design brief](docs/website.md) | Visual system and a responsive local prototype |
| [Current plan](PLAN.md) · [Experiment history](EXPERIMENTS.md) | Authoritative execution state and historical evidence (Chinese) |

## Built on prior work

HumanMimic integrates [NVIDIA SONIC / GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl), [GEM-X](https://github.com/NVlabs/GEM-X), SOMA/SMPL body representations and [MuJoCo](https://github.com/google-deepmind/mujoco). It does not train a replacement foundation controller. See [UPSTREAM.json](UPSTREAM.json), [.gitmodules](.gitmodules) and [asset and attribution notes](docs/getting-started.md#assets-and-attribution) for the implementation boundary.

This is currently a private research repository. Third-party code, weights, body models and source videos retain their own terms. No blanket license or redistribution permission is implied.
