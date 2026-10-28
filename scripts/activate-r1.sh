# Source this file from Bash: source scripts/activate-r1.sh
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Use: source scripts/activate-r1.sh" >&2
    exit 1
fi
_r1_project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$_r1_project_root/.local/miniforge3/etc/profile.d/conda.sh" ]]; then
    echo "Project Miniforge is missing; see README.md." >&2
    unset _r1_project_root
    return 1
fi
source "$_r1_project_root/.local/miniforge3/etc/profile.d/conda.sh"
conda activate "$_r1_project_root/.local/miniforge3/envs/humanoid-r1" || return
export CYCLONEDDS_HOME="$_r1_project_root/.local/unitree-dds"
export MUJOCO_GL=egl
export PYTHONNOUSERSITE=1
export TensorRT_ROOT="$_r1_project_root/.local/tensorrt-10.13.3"
export onnxruntime_ROOT="$_r1_project_root/.local/onnxruntime-linux-x64-1.22.0"
export CUDA_HOME="$CONDA_PREFIX"
export CUDAToolkit_ROOT="$CONDA_PREFIX"
export CMAKE_PREFIX_PATH="$CONDA_PREFIX${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
_r1_library_paths="$TensorRT_ROOT/lib:$onnxruntime_ROOT/lib:$_r1_project_root/.local/unitree-dds-lib:$_r1_project_root/vendor/GR00T-WholeBodyControl/gear_sonic_deploy/thirdparty/unitree_sdk2/thirdparty/lib/x86_64:$CONDA_PREFIX/lib"
for _r1_library_dir in "$CONDA_PREFIX"/lib/python3.10/site-packages/nvidia/*/lib; do
    [[ -d "$_r1_library_dir" ]] && _r1_library_paths+=":$_r1_library_dir"
done
export LD_LIBRARY_PATH="$_r1_library_paths${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset _r1_library_paths _r1_library_dir
unset _r1_project_root
