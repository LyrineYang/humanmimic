"""CUDA modality boundary before memory selection or belief preparation.

The immutable collector stream retains full forces. V sees no tactile records;
VB sees only thresholded per-taxel bits, timing, known hand frames and health.
No continuous force vectors survive in a VB estimation/memory input.
"""
import torch
from r4_public import validate_frame


def observation_view(frames, calibration, modality, device):
    if device.type != "cuda" or modality not in {"V", "VB", "VF"}:
        raise ValueError("An explicit CUDA modality is required")
    output, previous = [], -1.
    for frame in frames:
        projected = any("contact_bits" in packet for packet in frame["tactile"])
        validate_frame(frame, previous, tactile_mode="binary" if projected else "force")
        previous = frame["time_s"]
        if projected and modality != "VB":
            raise ValueError("Binary records cannot stand in for an acquired force stream")
        if modality == "VF":
            output.append(frame)
            continue
        packets = []
        if modality == "VB":
            for packet in frame["tactile"]:
                if projected:
                    packets.append(packet)
                    continue
                binary = {key: value for key, value in packet.items() if key != "force_sensor_n"}
                bits = None
                if packet["valid"]:
                    force = torch.tensor(packet["force_sensor_n"], device=device, dtype=torch.float64)
                    width, height = calibration["size"]
                    if force.shape != (height, width, 3):
                        raise ValueError("Invalid force grid at modality boundary")
                    bits = (force.norm(dim=-1) >= calibration["threshold_n"]).tolist()
                binary["contact_bits"] = bits
                packets.append(binary)
        output.append({**frame, "tactile": packets})
    return output
