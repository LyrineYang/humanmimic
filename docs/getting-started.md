# Getting started

[Home](../README.md) / Setup · [Usage](usage.md) · [Troubleshooting](troubleshooting.md)

Choose the path that matches what you want to do. You can explore the project without a GPU; running motion extraction and physical simulation needs the prepared runtime described below.

| I want to… | Start here |
| :--- | :--- |
| See what the output looks like | [Demo and results](results.md) — no installation |
| Understand or modify the pipeline | [Clone the source](#get-the-source), then [architecture](architecture.md) |
| Run a video on a prepared machine | [Usage: video to simulation](usage.md#video-to-simulation) |
| Set up another workstation or server | [Prepare a runtime](#prepare-a-runtime) |
| Fix a setup or execution problem | [Troubleshooting](troubleshooting.md) |

## Get the source

You need Git, Git LFS and access to this private repository. Use your existing GitHub authentication; no credentials belong in the project files.

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --recurse-submodules https://github.com/LyrineYang/humanmimic.git
cd humanmimic
git submodule status
```

For an existing checkout after the repository rename, follow the [handoff synchronization guide](../REMOTE_WORK.md). Compare the checkout commit with `main` and `codex/linux-handoff`; do not globally replace archived filesystem paths or rewrite frozen manifests.

This fetches source while skipping large LFS objects. It does **not** install the runtime or obtain pretrained weights, body models, full source videos or previous run packages.

| Location | What you will find |
| :--- | :--- |
| `scripts/` | Extraction, execution, evaluation and recovery entry points |
| `configs/` | Dependency snapshots, source lists, annotations and evaluation rules |
| `evidence/` | Compact results and artifact hashes; readable without GPU packages |
| `docs/` | Setup, usage, troubleshooting, architecture and research notes |
| `vendor/` | Pinned SONIC and GEM-X submodules |
| `website/` | Static presentation prototype |

## Prepare a runtime

**Setup is currently manual.** The accepted baseline ran on an RTX 4060 Laptop (8188 MiB) under WSL2. There is no portable installer or accepted fresh-machine rebuild yet. The original workstation's new GPU execution is now paused for server migration; the execution policy checks boot identity before even a video `--check-only` call. See the [Linux migration handoff](../HANDOFF.md) for current target readiness.

Preparation has four parts. A Python package install alone does not supply the native controller or model assets.

| Part | What must be ready | Source of truth |
| :--- | :--- | :--- |
| **1. Source** | Pinned SONIC/GEM-X checkouts, real G1 LFS assets and the existing simulation DDS patch | [.gitmodules](../.gitmodules), [UPSTREAM.json](../UPSTREAM.json), [patch](../patches/sonic-loopback-dds.patch) |
| **2. Control runtime** | R1 Conda environment, compiled SONIC C++ controller, TensorRT/ORT C++ libraries and matched CycloneDDS/Unitree SDK | [R1 environment](../configs/environment-r1.yml), [native dependencies](../configs/r1-native-dependencies.json), [workstation build notes](operations.zh-CN.md) |
| **3. Perception runtime** | Separate R2 Conda environment and pinned GEM-X/SOMA dependencies | [R2 environment](../configs/environment-r2.yml), [constraints](../configs/constraints-r2.txt), [package snapshot](../configs/requirements-r2.lock.txt) |
| **4. Assets and storage** | Policy/observation assets, perception/body-model weights, data volume, verified ownership and target-specific resource configuration | [Asset inventory](../HANDOFF.md#52-git克隆不会带来的内容), [R1 asset hashes](../configs/r1-suite.json), [R2 resource configuration](../configs/r2-resources.json) |

The baseline uses two environments because perception and control have different dependency requirements:

| | Controller / simulation | Motion extraction |
| :--- | :--- | :--- |
| Activation | `source scripts/activate-r1.sh` | `source scripts/activate-r2.sh` |
| Baseline Python | 3.10 | 3.12 |
| Main dependencies | MuJoCo 3.3.7, TensorRT 10.13.3.9, ORT C++ 1.22.0 | GEM-X, PyTorch 2.10.0+cu128, SOMA 0.3.3 |
| Baseline prefix | `.local/miniforge3/envs/humanoid-r1` | `/mnt/d/humanoid-demo-r2/envs/humanoid-r2` |

[R1 pip snapshot](../configs/requirements-r1.lock.txt) · [R2 exact Conda packages](../configs/conda-r2-linux-64.explicit.txt)

Keep the environments separate. The snapshots describe the accepted installation; they are not a complete cross-platform installation recipe. The current R2 resource checks reference `/mnt/c` and `/mnt/d`, storage ownership and the authorized boot identity. Setting `R2_STORAGE_ROOT` by itself is not a server port. Adapt and validate those assumptions through the migration process rather than creating empty marker files or disabling checks.

### Verify the prepared target

After its environment and execution authorization are ready, activate R1 and run the existing environment check into a new directory:

```bash
source scripts/activate-r1.sh
python scripts/check-r1-environment.py --output runs/r1-environment-NEW
```

This check performs CUDA computation, model loading and a short basic physics/rendering check. It is **not** a read-only inventory command and does not certify SONIC tracking. Do not use it to restart GPU work on the paused source workstation. The subsequent [reference-motion recipe](usage.md#reference-motion-to-simulation) exercises the controller; only then proceed to a new video.

### Resource expectations

- The verified workflow is **offline** and uses perception stages sequentially before control. An 8 GB GPU result is not a promise for arbitrary hardware, video length or concurrent camera operation.
- The existing data-volume plan reserves approximately **100 GiB** for preparation and experiments, with configured free-space floors of **10 GiB on C** and **20 GiB on D**. A server needs its own storage mapping.
- Full processing is much slower than the source clip. The accepted five-video held-out queue took about **158 minutes** on the original setup; this is context, not a per-video timeout or latency guarantee.
- Current videos use software-rendered actual-state playback. GPU window rendering and live-camera operation remain unverified.

## Make your first run

Use a short, single-person, fixed-camera video with the full body and feet visible on a level floor. The current limit is 60 seconds; longer sources are rejected rather than silently cut.

Follow [Video to simulation](usage.md#video-to-simulation) for the command, preflight fields and output directory. Start without event annotations for exploration; add predeclared motion events before a measured evaluation. All five original held-out videos are already used and reserved for their suite workflow.

## Assets and attribution

SONIC and GEM-X retain their upstream licenses. Obtain pretrained policy, perception and SOMA/SMPL assets from authorized sources and keep their terms. Model files and credentials do not belong in Git. Source videos belong to their creators; full originals and run recordings are not bundled as a dataset.

This private repository does not yet have a project-wide open-source license. Integration code and small previews do not imply permission to redistribute third-party assets.

## Optional: preview the project website

From the repository root, without GPU packages:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/website/` on the same machine. Remote access needs supported forwarding. This is a local static prototype, not the execution UI. [Website design and publication notes](website.md)

The [historical operations guide](operations.zh-CN.md) preserves earlier workstation commands. Current readiness and migration instructions take precedence over its historical status.
