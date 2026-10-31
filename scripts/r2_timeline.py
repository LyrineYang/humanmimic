"""Full-source 30Hz normalization with verified selected input-frame identity."""

from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
import subprocess

from r2_common import sha256, write_json

FPS_SOURCE = "https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavfilter/vf_fps.c"


def read_framehash(path):
    timebase, frames = None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#tb 0:"):
            timebase = Fraction(line.split(":", 1)[1].strip())
        elif line and not line.startswith("#"):
            stream, dts, pts, duration, size, digest = [item.strip() for item in line.split(",")]
            frames.append({"pts": int(pts), "size": int(size), "hash": digest})
    if timebase is None or not frames:
        raise ValueError("Missing raw-frame timestamp/hash records")
    return timebase, frames


def near_inf(value):
    """Exact AV_ROUND_NEAR_INF for rational timestamps, including half ties."""
    if value < 0:
        return -near_inf(-value)
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def verify_mapping(source_hash, selected_hash):
    timebase, inputs = read_framehash(source_hash)
    output_tb, outputs = read_framehash(selected_hash)
    if output_tb != Fraction(1, 30) or inputs[0]["pts"] != 0:
        raise ValueError("Unexpected normalized timestamp origin/timebase")
    source_pts = [item["pts"] for item in inputs]
    if any(b <= a for a, b in zip(source_pts, source_pts[1:])):
        raise ValueError("Original raw frames require strictly increasing PTS")
    # Pinned fps filter rounds input PTS onto the output grid, then replaces
    # the queued frame when the following rounded PTS <= next output PTS.
    rounded = [near_inf(Fraction(pts) * timebase * 30) for pts in source_pts]
    indices = []
    for index, frame in enumerate(outputs):
        if frame["pts"] != index:
            raise ValueError("Output raw frames do not form the complete 30Hz grid")
        selected = bisect_right(rounded, frame["pts"]) - 1
        if selected < 0 or frame["hash"] != inputs[selected]["hash"] or frame["size"] != inputs[selected]["size"]:
            raise ValueError(f"fps selected-frame identity mismatch at output {index}")
        indices.append(selected)
    return {"status": "passed", "normalized_fps": 30, "source_time_base": str(timebase), "source_pts_after_startpts": source_pts, "source_pts_rounded_to_30hz": rounded, "normalized_times": [i / 30 for i in range(len(outputs))], "selected_source_frame_indices": indices, "source_frames": len(inputs), "normalized_frames": len(outputs), "selection_proof": "All pre-encode output raw-frame MD5 hashes/sizes equal the selected input decoded frames after even padding; exact rational fps rounding verified", "source_framehash_sha256": sha256(source_hash), "selected_framehash_sha256": sha256(selected_hash), "fps_filter_source": FPS_SOURCE, "source_content_trimmed": False, "time_shift_fitted": False}


def normalize(source, output):
    output = Path(output)
    # Hash raw frames in the same filter graph as the actual encoder. Nothing
    # writes decoded RGB/YUV sequences to disk, and no source interval is cut.
    graph = "[0:v]setpts=PTS-STARTPTS,pad=ceil(iw/2)*2:ceil(ih/2)*2,split=2[original][rate];[rate]fps=30:round=near,split=2[encoded][selected]"
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-filter_complex_threads", "1", "-i", str(source), "-filter_complex", graph,
               "-map", "[encoded]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(output / "normalized.mp4")]
    for label, filename in (("original", "source-framehash.csv"), ("selected", "selected-framehash.csv")):
        command += ["-map", f"[{label}]", "-c:v", "rawvideo", "-threads:v", "1", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-enc_time_base", "filter", "-f", "framemd5", str(output / filename)]
    write_json(output / "normalization-command.json", {"command": command, "ffmpeg_version": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0], "source_content_trimmed": False})
    subprocess.run(command, check=True)
    mapping = verify_mapping(output / "source-framehash.csv", output / "selected-framehash.csv")
    write_json(output / "selected-frame-mapping.json", mapping)
    return mapping
