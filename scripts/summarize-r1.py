"""Audit a complete R1 run using native lossless control logs and its video."""

import argparse
import csv
import json
from pathlib import Path
import subprocess

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    out = args.run.resolve()
    config = json.loads((out / "run-config.json").read_text())
    online = json.loads((out / "metrics.json").read_text())
    assert online["status"] == "passed" and online["motion_completed"]
    with (out / "controller-csv/q.csv").open() as f:
        qrows = list(csv.DictReader(f))
    with (out / "controller-csv/motion_playing.csv").open() as f:
        playing = {int(r["index"]) for r in csv.DictReader(f) if float(r["playing_0"]) > .5}
    with (out / "controller-reference.csv").open() as f:
        references = np.array([[float(v) for v in row if v] for row in csv.reader(f)])
    indices = np.array([int(r["index"]) for r in qrows])
    assert np.array_equal(indices, np.arange(len(qrows)))
    assert len(qrows) == len(references)
    # StateLogger::appendCsvLinesSplit_ already restores default offsets and
    # converts q.csv to measured MuJoCo/hardware order. Do not transform twice.
    measured = np.array([[float(r["q_" + str(i)]) for i in range(29)] for r in qrows])
    reference = references[:, 7:36]
    packets = [json.loads(line) for line in (out / "controller-output.jsonl").read_text().splitlines()]
    common = [p for p in packets if p["payload"]["index"] in playing]
    ci = np.array([p["payload"]["index"] for p in common])
    zm = np.array([p["payload"]["body_q_measured"] for p in common])
    zr = np.array([p["payload"]["body_q_target"] for p in common])
    measured_delta = float(np.max(abs(measured[ci] - zm)))
    reference_delta = float(np.max(abs(reference[ci] - zr)))
    assert measured_delta < 1e-7, measured_delta
    assert reference_delta < 1e-5, reference_delta
    mask = np.isin(indices, list(playing))
    assert int(mask.sum()) == config["reference_frames"]
    error = np.arctan2(np.sin(measured[mask] - reference[mask]),
                       np.cos(measured[mask] - reference[mask]))
    assert np.isfinite(error).all()
    rmse = float(np.sqrt(np.mean(error ** 2)))
    assert rmse <= config["joint_rmse_max_rad"]
    stamps = np.array([float(r["time_monotonic_ms"]) / 1000 for r in qrows])[mask]
    full = {
        "status": "passed", "control_samples": int(mask.sum()),
        "joint_rmse_rad": rmse, "joint_rmse_limit_rad": config["joint_rmse_max_rad"],
        "all_motion_frames_present": True, "online_packet_sample_count": len(common),
        "online_packet_missing_indices": sorted(playing - set(ci.tolist())),
        "csv_vs_zmq_measured_max_delta_rad": measured_delta,
        "csv_vs_zmq_reference_max_delta_rad": reference_delta,
        "alignment": "Native actual q.csv and controller-reference.csv from the same control tick; consecutive indices verified. Native q.csv is already in measured MuJoCo order, checked against all available ZMQ samples. No time shift or threshold change.",
        "per_joint_rmse_rad": np.sqrt(np.mean(error ** 2, axis=0)).tolist(),
    }
    (out / "full-sample-metrics.json").write_text(json.dumps(full, indent=2) + "\n")
    np.savez_compressed(out / "full-sample-tracking.npz", controller_index=indices[mask],
                        monotonic=stamps, measured_joint_position=measured[mask],
                        reference_joint_position=reference[mask], angular_error=error)
    for filename, header, rows in [
        ("joint-metrics.csv", ["joint", "rmse_rad"],
         zip(config["joint_names_mujoco_order"], full["per_joint_rmse_rad"])),
        ("tracking-rmse.csv", ["controller_index", "elapsed_seconds", "rmse_rad"],
         zip(indices[mask], stamps - stamps[0], np.sqrt(np.mean(error ** 2, axis=1)))),
    ]:
        with (out / filename).open("w") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    video = out / "actual-execution.mp4"
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,duration,r_frame_rate",
                            "-of", "json", str(video)], capture_output=True, text=True, check=True)
    video_info = json.loads(probe.stdout)
    (out / "video-probe.json").write_text(json.dumps(video_info, indent=2) + "\n")
    stream = video_info["streams"][0]
    expected = config["reference_frames"] / config["control_hz"]
    assert stream["codec_name"] == "h264"
    assert float(stream["duration"]) >= expected - .08
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                            capture_output=True, text=True)
    (out / "video-decode-check.txt").write_text(decode.stdout + decode.stderr)
    assert decode.returncode == 0 and not decode.stderr
    report = f"""# R1 单次完整复现结果

状态：**passed（本轮完整环境配置与单动作复现）**。原计划五动作、每动作两次的 R1 整体验收仍为 awaiting_verification。

| 项目 | 实测 |
| --- | --- |
| 动作 | {config['motion_name']}，官方样例/调试动作 |
| 完整参考帧 | {full['control_samples']} / {config['reference_frames']} |
| 名义动作时长 | {expected:.2f} 秒 |
| 全动作 29 关节 RMSE | {rmse:.6f} rad，门槛 ≤{config['joint_rmse_max_rad']:.2f} rad |
| 跌倒 / 跟踪中止 | 否 / 否 |
| 播放期间弹力带 | 关闭 |
| 根部、重力、接触 | 自由根部、重力与接触启用 |
| 实际状态覆写 | 无；执行由官方 TensorRT 策略与物理扭矩驱动 |
| 录像 | H.264，{stream['width']}×{stream['height']}，{stream['r_frame_rate']} fps，{stream['duration']} 秒 |
| 新增云费用 | 0 美元 |

环境：Windows 主机 zhen / WSL2 / Ubuntu 24.04.4，RTX 4060 Laptop。Python 3.10 conda 环境 humanoid-r1；TensorRT 10.13.3、CUDA 开发工具 12.8、ONNX Runtime C++ 1.22.0、MuJoCo 3.3.7。源码固定提交 {config['upstream_commit']}，仅加入仿真专用 DDS 配置入口；原策略权重、控制增益和动作数据未修改。

## 结果文件

- [完整动作录像](actual-execution.mp4)：执行结束后离屏渲染记录的真实 MuJoCo 状态，使用 CPU 软件渲染。它没有以参考姿态代替实际状态，也不代表 GPU 图形加速通过。
- [全部控制样本指标](full-sample-metrics.json) 与 [全量对齐实际值/参考值](full-sample-tracking.npz)。
- [逐关节 RMSE](joint-metrics.csv)、[逐帧 RMSE](tracking-rmse.csv)。
- [物理状态轨迹](actual-state.npz)、[原生控制器 CSV](controller-csv/q.csv)、[参考值 CSV](controller-reference.csv)。
- [运行配置与版本校验](run-config.json)、[真实启动命令](commands.json)、[官方控制器日志](controller.log)、[仿真日志](simulator.log)。

原生 CSV 保留全部 {full['control_samples']} 个播放样本。在线 ZMQ 日志收到了 {len(common)} 个，其中缺少的控制索引是 {full['online_packet_missing_indices']}；报告使用完整的原生 CSV，并对全部共同样本逐项校验，实际值最大差 {measured_delta:.2g} rad，参考值最大差 {reference_delta:.2g} rad（CSV 输出精度）。两份日志同一控制时刻对齐，没有拟合时间平移或放宽误差门槛。

## 复跑

从项目根目录执行，结果目录使用一个尚不存在的新名称：

```bash
source scripts/activate-r1.sh
python scripts/run-r1-reproduction.py --output runs/r1-new-reproduction
python scripts/summarize-r1.py --run runs/r1-new-reproduction
```

本次属于官方数据集动作复现，未运行视频感知、现场相机、真机或训练。预检失败与修复证据分别保存在 r1-preflight-20261028-01/02/03；第 04 轮 10 秒预检通过后才运行本次完整动作。
"""
    (out / "REPORT.md").write_text(report)
    audit = {"status": "passed", "motion_completed": True, "all_frames_audited": True,
             "video_decodes": True, "video": video_info, "full_sample_rmse_rad": rmse,
             "scope": "One full motion; five-motion R1 acceptance remains pending."}
    (out / "completion-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(full, indent=2))


if __name__ == "__main__":
    main()
