#!/usr/bin/env bash
# Source this file. Independent cloned prefix; never pip-install into r4-core.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' 'Use: source scripts/activate-vividex-demo.sh' >&2
  exit 1
fi
_vividex_scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${_vividex_scripts}/activate-r4-research.sh" || return 1
_vividex_prefix="${R4_DATA_ROOT}/envs/vividex-demo"
[[ -x "${_vividex_prefix}/bin/python" ]] || return 1
source "${R4_ENV_PREFIX}/etc/profile.d/conda.sh" || return 1
conda activate "${_vividex_prefix}" || return 1
export VIVIDEX_ENV_PREFIX="${_vividex_prefix}"
export LD_LIBRARY_PATH="${_vividex_prefix}/lib"
for _vividex_lib in "${_vividex_prefix}"/lib/python*/site-packages/nvidia/*/lib; do
  [[ ! -d "${_vividex_lib}" ]] || LD_LIBRARY_PATH+=":${_vividex_lib}"
done
export WANDB_MODE=offline MUJOCO_GL=egl
unset _vividex_scripts _vividex_prefix _vividex_lib
