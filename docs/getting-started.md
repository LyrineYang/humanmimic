# Getting started

[Home](../README.md) / Reproduce

The execution paths below were accepted on the existing WSL2 workstation. A fresh-machine rebuild has **not** been accepted. Clone the source to inspect the project; prepare the pinned environments and required assets before running the simulation commands.

## Inspect the repository

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --recurse-submodules https://github.com/LyrineYang/humanoid-demo.git
cd humanoid-demo
git submodule status
```

This private repository requires access through your existing GitHub authentication. The command skips automatic LFS downloads; it does not provide policy weights, licensed body-model assets, videos, environments or `runs/` evidence packages.

| Directory | Contents |
| :--- | :--- |
| `scripts/` | Setup checks, extraction, execution, evaluation and recovery |
| `configs/` | Environment snapshots, frozen source lists, annotations and evaluation rules |
| `evidence/` | Small acceptance summaries and provenance hashes tracked in Git |
| `docs/` | English project narrative, diagrams and reproducibility guidance |
| `website/` | Local static project-site prototype; no build step or hosted deployment |
| `vendor/` | Pinned upstream source submodules |
| `runs/`, `.local/` | Ignored local artifacts and runtime dependencies |

## Verified execution environment

The accepted runs used an **RTX 4060 Laptop (8188 MiB)** under **WSL2**, driver **617.42**. R1 uses Python 3.10, MuJoCo 3.3.7, TensorRT 10.13.3.9, CUDA development tools 12.8.93 and ONNX Runtime C++ 1.22.0. The simulation renderer used Mesa llvmpipe; GPU window rendering remains unverified.

| Environment | Definitions | Local layout |
| :--- | :--- | :--- |
| R1 controller/simulation | [Conda](../configs/environment-r1.yml), [constraints](../configs/constraints-r1.txt), [pip snapshot](../configs/requirements-r1.lock.txt) | `.local/miniforge3/envs/humanoid-r1` plus native dependencies |
| R2 motion extraction | [Conda](../configs/environment-r2.yml), [constraints](../configs/constraints-r2.txt), [exact Conda packages](../configs/conda-r2-linux-64.explicit.txt), [pip snapshot](../configs/requirements-r2.lock.txt) | `/mnt/d/humanoid-demo-r2/envs/humanoid-r2` |

R1 also requires the compiled C++ controller, matched policy/observation assets, SDK-compatible CycloneDDS libraries and the simulation-only [loopback DDS configuration](../configs/r1-dds.xml). The [upstream patch](../patches/sonic-loopback-dds.patch) is preserved; replacing DDS packages arbitrarily can break communication. Environment snapshots are evidence of installed versions, not a portable installer.

R2's activation script supports `R2_STORAGE_ROOT`, but resource checks still assume the current WSL storage layout. A different Linux server requires an explicit portability and compatibility pass. Do not interpret the reported four V100 cards as a verified target for the current TensorRT build.

## R1 on the prepared workstation

From the repository root, use a new output directory for every new attempt:

```bash
source scripts/activate-r1.sh
python scripts/check-r1-environment.py --output runs/r1-environment-NEW
python scripts/run-r1-reproduction.py --output runs/r1-reproduction-NEW
python scripts/summarize-r1.py --run runs/r1-reproduction-NEW
```

These commands check the environment and run one reference-motion reproduction. They do not repeat the full five-motion, two-trial acceptance suite. The fixed suite is defined in [r1-suite.json](../configs/r1-suite.json); preserve its inputs and evaluation rules when rerunning it. Read [PLAN.md](../PLAN.md) and inspect existing task/log state before starting work.

## R2 on the prepared workstation

Choose a single-person, fixed-camera, full-body video with visible feet and a level floor. The current pipeline accepts complete short sources up to its configured 60-second limit; it does not silently trim longer videos. Predeclare source-based motion events before evaluation. See [an example annotation](../configs/r2-debug-events-QqvZAUEOrAQ.json) for the source hash and `debug` role contract.

```bash
source scripts/activate-r2.sh
python scripts/run-r2-video.py \
  --input /absolute/path/to/input.mp4 \
  --run-id video-demo-NEW \
  --source-url 'https://example.com/original-source' \
  --events /absolute/path/to/source-events.json \
  --check-only
```

Inspect the scheduling/input report first; remove `--check-only` to execute. The events file must match the input's SHA256 and declare the `debug` role. Omitting annotations permits exploration but cannot satisfy full acceptance. Reserved held-out sources must use the frozen suite entry point, and all five original held-out sources are already marked used.

The pipeline writes complete stage caches, references, physical states, event/body metrics and a synchronized comparison under `$R2_STORAGE_ROOT/runs/video-demo-NEW/`. Existing terminal results are preserved. Failures remain failures even when the comparison MP4 renders successfully.

The main command uses the matched R1 environment for physical execution. Do not replace controller weights or move to a different machine and reuse an earlier acceptance label. [Results and local artifact index](results.md)

## Preview the future project site

No npm installation or GPU is required. From the repository root:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/website/` on that same machine. A remote host needs an explicit tunnel or supported port forwarding; another computer's loopback is not the preview. The prototype reads only repository assets and uses no analytics, remote fonts or application backend. [Design and publication handoff](website.md)

## Assets and attribution

SONIC and GEM-X remain pinned submodules with their upstream licenses. Obtain pretrained policy, perception and SOMA/SMPL assets from the corresponding authorized sources and retain their terms; do not commit model files or credentials. Source videos belong to their creators and are not bundled as a dataset. The small existing preview links to its original source in [results](results.md).

No repository-wide license has been selected for this private research project. Do not infer permission to redistribute third-party assets from the presence of integration code or a screenshot. Broader public release needs an explicit asset and licensing decision.

Detailed historical workstation notes remain available in [operations.zh-CN.md](operations.zh-CN.md). They are an archived copy of the earlier README; the current plan and English guides take precedence where historical status differs.
