"""Explicit GPU admission. There is deliberately no CPU fallback."""
import os
import subprocess
import torch


def require_cuda():
    selected = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not selected or "," in selected:
        raise RuntimeError("Select exactly one available GPU explicitly with CUDA_VISIBLE_DEVICES")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("CUDA unavailable; defer verification, never run a CPU substitute")
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    free, total = torch.cuda.mem_get_info(device)
    if free < 4 * 1024**3:
        raise RuntimeError("Less than 4 GiB free on selected GPU; do not disturb another workload")
    capability = torch.cuda.get_device_capability(device)
    if capability < (7, 0):
        raise RuntimeError("This implementation targets SM70 or newer")
    torch.set_num_threads(8)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats(device)
    return device, {"device": torch.cuda.get_device_name(device), "selected": selected,
        "capability": list(capability), "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "free_bytes_at_admission": free, "total_bytes": total,
        "nvidia_smi": subprocess.check_output(["nvidia-smi", "--query-gpu=uuid,name,memory.used,utilization.gpu,driver_version",
                                                 "--format=csv,noheader"], text=True).strip(),
        "cpu_fallback": False}
