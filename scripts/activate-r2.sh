#!/usr/bin/env bash
# Source this file; use --paths-only during installation.
_R2_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export R2_STORAGE_ROOT="${R2_STORAGE_ROOT:-/mnt/d/humanoid-demo-r2}"
export R2_CONDA_PREFIX="$R2_STORAGE_ROOT/envs/humanoid-r2"
export CONDA_PKGS_DIRS="$R2_STORAGE_ROOT/pkgs"
export CONDA_ENVS_PATH="$R2_STORAGE_ROOT/envs"
export CONDA_REGISTER_ENVS=false
export TMPDIR="$R2_STORAGE_ROOT/tmp"
export PIP_CACHE_DIR="$R2_STORAGE_ROOT/cache/pip"
export XDG_CACHE_HOME="$R2_STORAGE_ROOT/cache"
export HF_HOME="$R2_STORAGE_ROOT/cache/huggingface"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TORCH_HOME="$R2_STORAGE_ROOT/cache/torch"
export HF_XET_CACHE="$R2_STORAGE_ROOT/cache/huggingface/xet"
export CUDA_CACHE_PATH="$R2_STORAGE_ROOT/cache/cuda"
export TRITON_CACHE_DIR="$R2_STORAGE_ROOT/cache/triton"
export TORCH_EXTENSIONS_DIR="$R2_STORAGE_ROOT/cache/torch-extensions"
export TORCHINDUCTOR_CACHE_DIR="$R2_STORAGE_ROOT/cache/torch-inductor"
export MPLCONFIGDIR="$R2_STORAGE_ROOT/cache/matplotlib"
export NUMBA_CACHE_DIR="$R2_STORAGE_ROOT/cache/numba"
export PYTHONPYCACHEPREFIX="$R2_STORAGE_ROOT/cache/pycache"
export PYTHONNOUSERSITE=1
export TOKENIZERS_PARALLELISM=false
export TORCH_ALLOW_TF32_CUBLAS_OVERRIDE=0
export GEMX_ROOT="$_R2_PROJECT_ROOT/vendor/GEM-X"
export SONIC_ROOT="$_R2_PROJECT_ROOT/vendor/GR00T-WholeBodyControl"
# The conversion helper adds SONIC explicitly. Keeping it off this global path
# prevents pip from treating the R1 source tree's metadata as an R2 install.
export PYTHONPATH="$GEMX_ROOT"
if [[ "${1:-}" != "--paths-only" ]]; then
    if [[ ! -x "$R2_CONDA_PREFIX/bin/python" ]]; then
        echo "R2 environment missing: $R2_CONDA_PREFIX" >&2
        return 1 2>/dev/null || exit 1
    fi
    source "$_R2_PROJECT_ROOT/.local/miniforge3/etc/profile.d/conda.sh"
    conda activate "$R2_CONDA_PREFIX"
    export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:/usr/lib/wsl/lib"
    for _r2_library in "$CONDA_PREFIX"/lib/python*/site-packages/nvidia/*/lib; do
        [[ ! -d "$_r2_library" ]] || export LD_LIBRARY_PATH="$_r2_library:$LD_LIBRARY_PATH"
    done
fi
unset _R2_PROJECT_ROOT _r2_library
