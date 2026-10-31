"""Make full-timeline source / extracted 2D+3D / recorded-physics comparison."""

import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
import torch

from r2_common import write_json, storage_check

PARENTS = (-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21)


def fit(frame, width, height):
    output = np.zeros((height, width, 3), dtype=np.uint8)
    scale = min(width / frame.shape[1], height / frame.shape[0])
    new_width, new_height = round(frame.shape[1] * scale), round(frame.shape[0] * scale)
    resized = cv2.resize(frame, (new_width, new_height))
    x, y = (width - new_width) // 2, (height - new_height) // 2
    output[y:y + new_height, x:x + new_width] = resized
    return output


def title(frame, text, y=23):
    cv2.putText(frame, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)


def encoder(path, width, height, fps, log):
    return subprocess.Popen(["ffmpeg", "-hide_banner", "-nostdin", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)], stdin=subprocess.PIPE, stderr=log, stdout=log)


def main(args):
    source = args.extraction.resolve()
    physical = args.physical.resolve()
    storage_check(args.output)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    conversion = json.loads((source / "conversion.json").read_text())
    metadata = json.loads((source / "source.json").read_text())
    metrics = json.loads((physical / "physical-metrics.json").read_text())
    joints = np.load(source / "soma-joints.npz")
    points = torch.load(source / "keypoints2d.pt", map_location="cpu", weights_only=True).numpy()
    tracks = torch.load(source / "tracks.pt", map_location="cpu", weights_only=False)
    # The original native77 layout is the same public SOMA layout used by the
    # selected release. Resolve names, rather than inventing another ordering.
    from gem.motion.frontend.joint_sets import SOMA77_JOINT_NAMES
    from r2_smpl import build_soma_to_smpl_index
    point_map = build_soma_to_smpl_index(list(SOMA77_JOINT_NAMES))
    joint_map = conversion["smpl_indices"]
    capture = cv2.VideoCapture(str(source / "normalized.mp4"))
    robot_path = physical / "actual-execution.mp4"
    robot = cv2.VideoCapture(str(robot_path)) if robot_path.exists() else None
    fps, height = 25, 480
    duration = metadata["normalized"]["duration"]
    count = int(np.ceil(duration * fps))
    outputs = [("source-panel.mp4", 320), ("extraction-panel.mp4", 640), ("robot-panel.mp4", 640), ("comparison.mp4", 1600)]
    processes, logs, mapping = [], [], []
    try:
        for name, width in outputs:
            log = (output / (name + ".encode.log")).open("w")
            logs.append(log); processes.append(encoder(output / name, width, height, fps, log))
        for frame_index in range(count):
            t = frame_index / fps
            index = min(round(t * 30), len(points) - 1)
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"Source frame {index} cannot be decoded")
            original = fit(frame, 320, height)
            title(original, "Original video (full source)")
            overlay = frame.copy()
            for child, parent in enumerate(PARENTS):
                if parent < 0: continue
                a, b = points[index, point_map[child]], points[index, point_map[parent]]
                if min(a[2], b[2]) > 0.25:
                    cv2.line(overlay, tuple(np.rint(a[:2]).astype(int)), tuple(np.rint(b[:2]).astype(int)), (80, 240, 80), 3)
            for x, y, confidence in points[index]:
                if confidence > 0.25: cv2.circle(overlay, (round(float(x)), round(float(y))), 3, (0, 200, 255), -1)
            overlay = fit(overlay, 320, height)
            title(overlay, "Extracted 2D keypoints")
            observed = bool(tracks["observed_primary"][index])
            if not observed: title(overlay, "TRACK FILLED / INTERPOLATED", height - 14)
            skeleton = np.full((height, 320, 3), (32, 27, 24), dtype=np.uint8)
            xyz = joints["joints_world_yup_m"][index, joint_map]
            xyz = xyz - xyz[:1]
            projection = np.c_[160 + 155 * (xyz[:, 0] + 0.35 * xyz[:, 2]), 270 - 155 * xyz[:, 1]]
            for child, parent in enumerate(PARENTS):
                if parent >= 0:
                    color = (255, 180, 70) if "left" in conversion["joint_names"][joint_map[child]].lower() else (90, 170, 255)
                    cv2.line(skeleton, tuple(np.rint(projection[child]).astype(int)), tuple(np.rint(projection[parent]).astype(int)), color, 2)
            for point in projection: cv2.circle(skeleton, tuple(np.rint(point).astype(int)), 3, (240, 240, 240), -1)
            title(skeleton, "Estimated 3D body")
            title(skeleton, "Model estimate; not 3D truth", height - 14)
            extraction = np.hstack((overlay, skeleton))
            robot_panel = np.zeros((height, 640, 3), dtype=np.uint8)
            valid_robot = False
            if robot is not None and robot.isOpened():
                robot.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                robot_ok, robot_frame = robot.read()
                if robot_ok:
                    robot_panel = fit(robot_frame, 640, height)
                    valid_robot = True
            title(robot_panel, "Robot: recorded actual physics")
            if not valid_robot:
                title(robot_panel, "EXECUTION STOPPED / NO RECORDED FRAME", 240)
            for panel in (original, extraction, robot_panel): title(panel, f"Source time {t:.2f}s", height - 35)
            for process, panel in zip(processes, (original, extraction, robot_panel, np.hstack((original, extraction, robot_panel)))):
                process.stdin.write(np.ascontiguousarray(panel).tobytes())
            mapping.append({"demo_frame": frame_index, "source_time_s": t, "normalized_30hz_frame": index, "reference_50hz_frame": min(round(t * 50), conversion["control_frames"] - 1), "robot_frame_available": valid_robot})
        for process in processes:
            process.stdin.close()
            if process.wait(timeout=60): raise RuntimeError("Video encoding failed")
    finally:
        capture.release()
        if robot is not None: robot.release()
        for process in processes:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=15)
        for log in logs: log.close()
    write_json(output / "frame-mapping.json", mapping)
    write_json(output / "demo.json", {"status": "passed", "scope": "Full-timeline visualization generation; does not imply physical/extraction acceptance", "source_duration_s": duration, "frames": count, "fps": fps, "physical_status": metrics["status"], "extraction": str(source), "physical": str(physical), "source_content_trimmed": False, "time_shift_fitted": False, "robot_panel": "Recorded actual physics, rendered after execution; stopped frames explicitly blank", "audio": "Source audio retained in original; comparison is silent", "files": [name for name, _ in outputs]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
