#!/usr/bin/env bash
# Source; reuse the independent r4-core environment without changing global state.
_r4_research_script="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${_r4_research_script}/activate-r4.sh" || return 1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export TORCH_CUDA_ARCH_LIST="$(python -I -c 'import json,os; print(json.load(open(os.path.join(os.environ["R4_PROJECT_ROOT"], "configs/r4-runtime.json")))["target_compute_capability"])')"
export PYTHONDONTWRITEBYTECODE=1
export PYTORCH_KERNEL_CACHE_PATH="${R4_DATA_ROOT}/cache/torch-kernels"
export CUDA_CACHE_PATH="${R4_DATA_ROOT}/cache/cuda"
mkdir -p -- "${PYTORCH_KERNEL_CACHE_PATH}" "${CUDA_CACHE_PATH}" "${TMPDIR}"
# No default CUDA_VISIBLE_DEVICES: selection follows a fresh occupancy check.
unset _r4_research_script
