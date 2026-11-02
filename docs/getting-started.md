# Getting started

[Home](../README.md) / Setup · [Usage](usage.md) · [Troubleshooting](troubleshooting.md)

Start with the generated CUDA example to inspect the estimator without videos, body models or trained weights. Video imitation and LEAP manipulation have separate runtime and acceptance requirements.

## Get the source

Use an authorized checkout of this private repository:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/LyrineYang/humanmimic.git
cd humanmimic
```

The runtime work has been integrated into the local main line. The revision you check out must contain `scripts/humanmimic.py` and `configs/r4-bootstrap.json`; a checkout of an older default branch does not contain these commands. Local integration does not imply that GitHub has received the new commit. The analytic example does not use submodule assets or LFS downloads. Initialize the pinned submodules separately only when preparing the full video pipeline.

## Prepare a runtime

| Target | Supported scope | Separate limitations |
| --- | --- | --- |
| `r4-v100` | Linux x86_64, V100 SM70, Python 3.10.14, Torch 2.5.1+cu118; generated CUDA joint-estimation example | Requires an existing compatible NVIDIA driver; no CPU fallback |
| R4 research preview | LEAP sensing, joint estimation, memory and local control components | Additional public LEAP assets; successful manipulation and uncertainty calibration unverified |
| `legacy-wsl` | Historical RTX 4060 R1/R2 baseline and original storage/boot protection | New execution remains paused after the source machine reboot; R1/R2 server migration is unverified |

`python3` (3.6+) and Bash suffice for diagnosis/bootstrap; installed runtime commands use Python 3.10. The supported target needs at least 20 GiB free disk. Downloaded wheels total about 2.8 GiB; the installed prefix is about 6 GiB. Select a GPU with at least 4 GiB free for the bounded example. No driver installation, Docker, native source build or private asset is required for this example.

### How isolation is organized

One independent Conda prefix supplies Python and libraries; it is not a container. Activation discards inherited Python/user-site and library paths so another project cannot accidentally supply packages. The host NVIDIA driver is shared; CUDA 11.8 runtime libraries come from the pinned wheels. R1/R2 keep their separate historical environments.

| Location | Purpose |
| --- | --- |
| `humanmimic/` | Source, target profiles, lock files and small evidence summaries |
| `../humanmimic-data/r4/envs/r4-core` | Normal R4 runtime: Python 3.10.14, Torch 2.5.1+cu118, MuJoCo 3.2.7, W&B 0.22.3 |
| `../humanmimic-data/r4/{assets,cache,runs,tmp}` | Assets, download caches, large results and temporary files outside Git |
| `r4-rebuild-20261102` and `humanmimic-clean-data/r4/envs/r4-core` | Retained rebuild-verification prefixes; not additional runtime dependencies |

`r4-bootstrap.json` and `r4-pip-linux-x86_64.lock.txt` define installation; `r4-runtime.json` defines runtime bounds; `configs/targets/` selects machine paths and permitted workflows. Environment inventories are historical evidence, not extra installers. Keep local account settings and licensed assets outside Git. The [synchronization guide](../REMOTE_WORK.md) explains source updates separately from environment rebuilds.

### 1. Diagnose without running a model

```bash
python3 scripts/humanmimic.py doctor --target r4-v100
python3 scripts/humanmimic.py doctor --target r4-v100 --stage r2
```

Diagnosis exits 0 when inspection completes. Read `ready_to_attempt`, `dependencies`, `authorization`, `missing_runtime_paths` and `issues`. This is not CUDA or physics acceptance. A new Linux target can report missing R2 environments/assets without pretending to be the old WSL machine.

### 2. Rebuild an empty prefix

```bash
python3 scripts/humanmimic.py bootstrap \
  --prefix "$PWD/../humanmimic-data/r4/envs/r4-core" \
  --cache "$PWD/../humanmimic-data/r4/cache/bootstrap" \
  --output runs/install-r4-01
```

The installer verifies the pinned Miniforge archive and the hashes of every pip wheel, then runs `pip check`. It does not copy installed packages from another environment. A matching completed prefix is verified on a repeated call; an unrelated, modified or partial prefix is rejected and retained. Choose a new prefix/output for a new attempt. `--proxy URL` is optional and only applies to this invocation; no workstation proxy port is built into the installer. For offline installation, supply `--installer /path/to/Miniforge.sh --wheelhouse /path/to/original-wheels` with exactly the archived files named in the bootstrap manifest.

| File | Responsibility |
| --- | --- |
| [r4-bootstrap.json](../configs/r4-bootstrap.json) | Installer URL/SHA, wheel inventory, supported platform and asset/build requirements |
| [r4-pip-linux-x86_64.lock.txt](../configs/r4-pip-linux-x86_64.lock.txt) | Complete pip-managed layer with hashes, installed over the pinned Conda base |
| [conda-r4-linux-64.explicit.txt](../configs/conda-r4-linux-64.explicit.txt) | Baseline Conda package record; the hashed installer supplies this base |
| [requirements-r4-core.lock.txt](../configs/requirements-r4-core.lock.txt) | Historical full inventory including Conda packages; not a standalone pip installation input |
| [r4-runtime.json](../configs/r4-runtime.json) | Expected core versions, threads, CUDA architecture and research bounds |

Hash installation follows [pip's hash-checking contract](https://pip.pypa.io/en/stable/topics/secure-installs/); the Conda base is [Miniforge 24.3.0-0](https://github.com/conda-forge/miniforge/releases/tag/24.3.0-0).

### 3. Activate and select a device

```bash
# Set this only if you chose a different prefix:
# export R4_ENV_PREFIX=/absolute/path/to/your/prefix
source scripts/activate-r4-research.sh
nvidia-smi --query-gpu=uuid,name,memory.free,utilization.gpu --format=csv
```

Activation creates a fresh runtime boundary: it runs Conda activation hooks in a staging shell, removes external Python/user-package and stale library search paths, sets matching environment metadata, and publishes changes only on success. It deliberately replaces the caller's PATH with this environment plus standard system paths. Re-sourcing is supported; failure leaves the caller unchanged. Python user-site isolation uses [PYTHONNOUSERSITE](https://docs.python.org/3.10/using/cmdline.html#envvar-PYTHONNOUSERSITE). It is package isolation, not a security sandbox.

GPU selection is explicit for each invocation. The machine's GPU UUID and availability are not encoded in the target profile.

## Make your first run

Replace `GPU-...` with one available UUID from the inventory:

```bash
python scripts/humanmimic.py example \
  --target r4-v100 --gpu GPU-... --output runs/my-first-example
python3 scripts/humanmimic.py inspect runs/my-first-example
```

Open `runs/my-first-example/REPORT.md` and `comparison.svg`. The run preserves generated observations, the coarse prior, estimated state/covariance, private evaluation metrics, dependency/GPU identity and hashes. The diagram shows reconstruction, not robot execution. Full video reconstruction and grasping are not demonstrated by this example. [Output/status details](usage.md#cuda-example-and-results)

### Customize a target

Copy [r4-v100.json](../configs/targets/r4-v100.json) to ignored `configs/targets/my-server.local.json`, change storage/prefix/reserve paths, and pass that path as `--target`. Set `R4_ENV_PREFIX` for direct script activation, or pass `example --prefix` / `doctor --prefix`. Explicit profiles do not inherit old shell environment paths; the legacy WSL profile alone retains its historical `R2_STORAGE_ROOT` override. The `r4-v100` profile authorizes the local example/research preparation; it does not authorize R2 execution, paid resources or training. Preserve the original `legacy-wsl` boot policy and storage marker. Do not fabricate a marker or change a boot ID to make an old run execute.

### Separate video and LEAP setup

The full R1/R2 stack still needs the pinned SONIC/GEM-X sources, native controller, TensorRT/ORT/DDS libraries, policy/perception weights and licensed body assets. Use [R1 native dependencies](../configs/r1-native-dependencies.json), [R1 environment](../configs/environment-r1.yml), [R2 environment](../configs/environment-r2.yml), [asset inventory](../HANDOFF.md#52-git克隆不会带来的内容), and the [historical build notes](operations.zh-CN.md). R4 wheels do not supply that stack. The read-only [server inventory](server-readiness.zh-CN.md) is a dated migration snapshot, not the current R4 setup state.

The LEAP research path uses the public hand assets with their recorded upstream revision/hashes, described in the [R4 plan](r4-stage1.zh-CN.md). The generated example needs none. MANO remains separately licensed; keep it outside Git. Research commands and limits remain in the [multimodal protocol](r4-multimodal.zh-CN.md).

## Assets and attribution

This repository remains private and has no project-wide open-source license. Third-party code/assets retain their own terms. The installer downloads public package archives; it grants no new redistribution rights. Credentials, local W&B destinations, models and full private videos stay outside Git. Optional `configs/wandb.env` is ignored; the example forces local/offline logging and never uploads.

## Optional: preview the project website

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/website/` locally. This static prototype explains setup, outputs and research; it does not launch runs or imply a deployed website. [Website notes](website.md)
