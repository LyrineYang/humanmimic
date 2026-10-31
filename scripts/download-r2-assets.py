"""Download only the matched R2 body assets, with pinned metadata and SHA256 checks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def request(url, **headers):
    # The inherited desktop proxy is unavailable in this WSL session.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(urllib.request.Request(url, headers=headers), timeout=60)


def metadata(url):
    with request(url) as response:
        value = response.read(2 * 1024 * 1024 + 1)
    if len(value) > 2 * 1024 * 1024:
        raise ValueError("Unexpectedly large metadata response")
    return json.loads(value)


def download(item, target):
    expected, size = item.get("sha256"), item.get("bytes")
    if target.exists():
        actual = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
        if (size is None or target.stat().st_size == size) and (not expected or actual == expected):
            print(f"verified cache: {target.name}", flush=True)
            return actual
        raise ValueError(f"Existing final file has unexpected content: {target}")
    partial = target.with_name(target.name + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    digest = hashlib.sha256()
    if offset:
        with partial.open("rb") as previous:
            while block := previous.read(4 * 1024 * 1024):
                digest.update(block)
    if not size or offset < size:
        with request(item["url"], **headers) as response:
            if offset and response.status != 206:
                offset = 0
                digest = hashlib.sha256()
            if response.status == 206 and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                raise ValueError("Unexpected range response")
            started, logged, count = time.monotonic(), 0.0, offset
            with partial.open("ab" if offset else "wb") as output:
                while block := response.read(4 * 1024 * 1024):
                    output.write(block)
                    digest.update(block)
                    count += len(block)
                    if size and count > size:
                        raise ValueError(f"Download exceeded advertised size: {target.name}")
                    now = time.monotonic()
                    if now - logged >= 10:
                        rate = (count - offset) / max(now - started, 0.001) / 1024**2
                        print(f"{target.name}: {count / 1024**2:.1f} MiB, {rate:.1f} MiB/s", flush=True)
                        logged = now
                output.flush()
                os.fsync(output.fileno())
    actual = digest.hexdigest()
    if size and partial.stat().st_size != size:
        raise ValueError(f"Incomplete download: {target.name}")
    if expected and actual != expected:
        raise ValueError(f"SHA256 mismatch: {target.name}")
    os.replace(partial, target)
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path(os.environ.get("R2_STORAGE_ROOT", "/mnt/d/humanoid-demo-r2")))
    args = parser.parse_args()
    root = args.storage.resolve()
    if not (root / ".humanoid-demo-r2-owner.json").is_file():
        raise SystemExit("Use the approved dedicated R2 storage root")
    output = root / "runs/asset-download-20261030"
    output.mkdir(exist_ok=True)
    plan_path = output / "download-plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = {"status": "awaiting_verification", "repositories": {}, "files": [], "cloud_cost_usd": 0}
        groups = [
            ("nvidia/GEM-X", "main", "gem-x", ["body_s240000.ckpt", "vitpose.pth", "motion_native77_e774_s292175.ckpt", "body_config.json", "motion_stats_raw.npz", "motion_native77.yaml", "body_video_native77.yaml"]),
            ("nvidia/SOMA-X", "v0.3.3", "soma-v0.3.3", ["SOMA_neutral.npz", "SOMA_template_rig.usda", "SOMA_procedural_transforms.json", "correctives_model.pt"]),
        ]
        for repo, revision, directory, wanted in groups:
            info = metadata(f"https://huggingface.co/api/models/{repo}/revision/{revision}")
            pinned = info["sha"]
            tree = metadata(f"https://huggingface.co/api/models/{repo}/tree/{pinned}?recursive=true&expand=false")
            write_json(output / (directory + "-metadata.json"), {"repo": repo, "revision": pinned, "info": info, "tree": tree})
            by_name = {item["path"]: item for item in tree}
            plan["repositories"][repo] = {"requested_revision": revision, "pinned_revision": pinned}
            for name in wanted:
                item = by_name[name]
                plan["files"].append({"path": f"models/{directory}/{name}", "bytes": item["size"], "sha256": item.get("lfs", {}).get("oid"), "url": f"https://huggingface.co/{repo}/resolve/{pinned}/{name}"})
        url = "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_x_8xb8-300e_humanart-a39d44ed.zip"
        with request(url, Range="bytes=0-0") as response:
            total = response.headers.get("Content-Range", "").split("/")[-1]
            if not total.isdigit():
                total = response.headers.get("Content-Length")
        plan["files"].append({"path": "models/yolox_humanart.zip", "bytes": int(total) if total else None, "sha256": None, "url": url})
        plan["known_download_bytes"] = sum(item["bytes"] or 0 for item in plan["files"])
        plan["expectation"] = "Download only matched body weights and SOMA v0.3.3; verify all published LFS SHA256, retain source/size/hash, no inference or paid compute."
        if plan["known_download_bytes"] > 12 * 1024**3:
            raise ValueError("Asset plan exceeds reviewed size range; inspect before downloading")
        write_json(plan_path, plan)
    print(json.dumps({"download_gib": plan["known_download_bytes"] / 1024**3, "pins": plan["repositories"]}), flush=True)
    if shutil.disk_usage(root).free < plan["known_download_bytes"] + 20 * 1024**3:
        raise ValueError("Insufficient D host free space")
    started = time.monotonic()
    results = []
    try:
        for item in plan["files"]:
            target = root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            sha = download(item, target)
            results.append({"path": item["path"], "bytes": target.stat().st_size, "sha256": sha, "published_hash_verified": bool(item.get("sha256"))})
            write_json(output / "progress.json", {"status": "awaiting_verification", "completed": results})
        detector = root / "models/gem-x/yolox_humanart.onnx"
        if not detector.exists():
            with zipfile.ZipFile(root / "models/yolox_humanart.zip") as archive:
                names = [name for name in archive.namelist() if name.endswith("/end2end.onnx")]
                if len(names) != 1:
                    raise ValueError("Unexpected detector archive layout")
                with archive.open(names[0]) as source, detector.open("wb") as target:
                    shutil.copyfileobj(source, target, 4 * 1024 * 1024)
        results.append({"path": str(detector.relative_to(root)), "bytes": detector.stat().st_size, "sha256": hashlib.file_digest(detector.open("rb"), "sha256").hexdigest(), "published_hash_verified": False})
        write_json(output / "results.json", {"status": "passed", "scope": "Asset identity/download only; runtime not validated", "files": results, "wall_seconds_this_invocation": time.monotonic() - started, "cloud_cost_usd": 0})
    except Exception as error:
        write_json(output / "failure.json", {"status": "failed", "error": str(error), "completed": results, "partials_preserved": True})
        raise


if __name__ == "__main__":
    main()
