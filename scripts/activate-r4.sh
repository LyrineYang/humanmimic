#!/usr/bin/env bash
# Source from Bash. Prepare the whole boundary in a child shell, then publish it
# only after Conda hooks and directories succeed. Failure leaves the caller intact.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' 'Use: source scripts/activate-r4.sh' >&2
  exit 1
fi
_humanmimic_activate_r4() {
  local activation
  activation="$(
    set -e
    set +u
    project="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
    data="${R4_DATA_ROOT:-$(dirname -- "$project")/humanmimic-data/r4}"
    prefix="${R4_ENV_PREFIX:-$data/envs/r4-core}"
    if [[ ! -x "$prefix/bin/python" || ! -f "$prefix/etc/profile.d/conda.sh" ]]; then
      printf 'R4 Conda environment missing: %s\n' "$prefix" >&2
      exit 1
    fi
    prefix="$(cd -- "$prefix" && pwd -P)"
    unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONEXECUTABLE
    unset __PYVENV_LAUNCHER__ VIRTUAL_ENV LD_PRELOAD LD_LIBRARY_PATH
    unset CUDA_HOME CUDA_PATH CUDAToolkit_ROOT TensorRT_ROOT onnxruntime_ROOT CYCLONEDDS_HOME
    unset CMAKE_PREFIX_PATH PKG_CONFIG_PATH XML_CATALOG_FILES
    for name in ${!CONDA_@} ${!_CONDA_@}; do unset "$name"; done
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    export PYTHONNOUSERSITE=1
    source "$prefix/etc/profile.d/conda.sh" || exit 1
    conda activate "$prefix" >&2 || exit 1
    export R4_PROJECT_ROOT="$project" R4_DATA_ROOT="$data" R4_ENV_PREFIX="$prefix"
    export TMPDIR="$data/tmp" PIP_CACHE_DIR="$data/cache/pip"
    export XDG_CACHE_HOME="$data/cache" HF_HOME="$data/cache/huggingface"
    export TORCH_HOME="$data/cache/torch" MPLCONFIGDIR="$data/cache/matplotlib"
    export LD_LIBRARY_PATH="$prefix/lib"
    export CMAKE_PREFIX_PATH="$prefix" PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
    for library in "$prefix"/lib/python*/site-packages/nvidia/*/lib; do
      [[ ! -d "$library" ]] || LD_LIBRARY_PATH+=":$library"
    done
    threads="$("$prefix/bin/python" -I -c 'import json,sys; v=json.load(open(sys.argv[1]))["cpu_threads"]; assert type(v) is int and 1<=v<=64; print(v)' "$project/configs/r4-runtime.json")" || exit 1
    export OMP_NUM_THREADS="$threads" MKL_NUM_THREADS="$threads" OPENBLAS_NUM_THREADS="$threads"
    export MUJOCO_GL=egl PYTHONDONTWRITEBYTECODE=1
    # This ignored file belongs to the user. No account/credentials are shipped.
    export WANDB_DIR="$data/runs/wandb"
    if [[ -f "$project/configs/wandb.env" ]]; then source "$project/configs/wandb.env" || exit 1; fi
    mkdir -p -- "$TMPDIR" "$PIP_CACHE_DIR" "$HF_HOME" "$TORCH_HOME" "$MPLCONFIGDIR" "$WANDB_DIR" || exit 1
    printf '%s\n' 'unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONEXECUTABLE __PYVENV_LAUNCHER__ VIRTUAL_ENV LD_PRELOAD CUDA_HOME CUDA_PATH CUDAToolkit_ROOT TensorRT_ROOT onnxruntime_ROOT CYCLONEDDS_HOME'
    printf '%s\n' 'for _hm_old in ${!CONDA_@} ${!_CONDA_@}; do unset "$_hm_old"; done; unset _hm_old'
    for name in PATH CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_EXE CONDA_PYTHON_EXE CONDA_PROMPT_MODIFIER \
      R4_PROJECT_ROOT R4_DATA_ROOT R4_ENV_PREFIX TMPDIR PIP_CACHE_DIR XDG_CACHE_HOME HF_HOME TORCH_HOME MPLCONFIGDIR \
      LD_LIBRARY_PATH CMAKE_PREFIX_PATH PKG_CONFIG_PATH XML_CATALOG_FILES PYTHONNOUSERSITE PYTHONDONTWRITEBYTECODE \
      OMP_NUM_THREADS MKL_NUM_THREADS OPENBLAS_NUM_THREADS MUJOCO_GL WANDB_DIR WANDB_ENTITY WANDB_PROJECT; do
      if [[ -v "$name" ]]; then printf 'export %s=%q\n' "$name" "${!name}"; else printf 'unset %s\n' "$name"; fi
    done
  )" || return 1
  eval "$activation"
  hash -r
}
if _humanmimic_activate_r4; then
  unset -f _humanmimic_activate_r4
else
  unset -f _humanmimic_activate_r4
  return 1
fi
