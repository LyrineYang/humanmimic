"""Download private draft assets with gh, resume by chunk, verify and reassemble."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(4*1024**2), b""): h.update(data)
    return h.hexdigest()


def valid(path, item):
    return path.is_file() and not path.is_symlink() and path.stat().st_size == item["size"] and digest(path) == item["sha256"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--parts-dir", type=Path)
    args = p.parse_args()
    data = json.loads(args.manifest.read_text())
    if not data["complete_source_manifest"]: p.error("This transfer manifest is incomplete")
    repo, rid = data["repository"], data["release_id"]
    release = json.loads(subprocess.check_output(["gh", "api", f"repos/{repo}/releases/{rid}"]))
    if not release["draft"]: p.error("Release is no longer a private draft; review its access state")
    assets = {a["name"]: a for a in release["assets"]}
    args.output.mkdir(parents=True, exist_ok=True)
    parts = args.parts_dir or args.output / "parts"; parts.mkdir(parents=True, exist_ok=True)
    results = []
    for archive in data["archives"]:
        relative = Path(archive["path"])
        if relative.is_absolute() or ".." in relative.parts: p.error("Unsafe archive path")
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not valid(destination, archive):
            for piece in archive["parts"]:
                name = piece["name"]
                if Path(name).name != name: p.error("Unsafe asset name")
                local = parts / name
                if valid(local, piece): continue
                asset = assets[name]
                if asset["size"] != piece["size"] or asset.get("digest") != "sha256:"+piece["sha256"]:
                    p.error("Remote asset metadata differs: "+name)
                temporary = local.with_name(local.name+".downloading")
                with temporary.open("wb") as out:
                    subprocess.run(["gh", "api", f"repos/{repo}/releases/assets/{asset['id']}", "-H", "Accept: application/octet-stream"], stdout=out, check=True)
                if not valid(temporary, piece): p.error("Downloaded part checksum differs: "+name)
                temporary.replace(local)
                print(name, "downloaded and verified", flush=True)
            temp = destination.with_name(destination.name+".assembling")
            with temp.open("wb") as out:
                for piece in archive["parts"]:
                    with (parts / piece["name"]).open("rb") as src: shutil.copyfileobj(src, out, 4*1024**2)
            if not valid(temp, archive): p.error("Reassembled archive checksum differs")
            temp.replace(destination)
        results.append(dict(path=archive["path"], status="passed", size=archive["size"], sha256=archive["sha256"]))
        print(archive["path"], "archive verified", flush=True)
    (args.output / "download-verification.json").write_text(json.dumps({"status":"passed","archives":results},indent=2)+"\n")


if __name__ == "__main__": main()
