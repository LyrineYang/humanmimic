#!/usr/bin/env bash
# Full local video pipeline; a failed physical run still gets a truthful demo.
set -euo pipefail
_r2_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 2 ]]; then
    echo "Usage: bash scripts/run-r2-demo.sh INPUT_VIDEO RUN_ID [SOURCE_URL]" >&2
    exit 2
fi
_r2_input="$(realpath -- "$1")"
_r2_id="$2"
if [[ ! "$_r2_id" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
    echo "RUN_ID must be a simple directory name" >&2
    exit 2
fi
source "$_r2_root/scripts/activate-r2.sh"
_r2_output="$R2_STORAGE_ROOT/runs/$_r2_id"
mkdir -p "$_r2_output"
_r2_source_args=()
if [[ $# -ge 3 ]]; then _r2_source_args=(--source-url "$3"); fi
python "$_r2_root/scripts/extract-r2-video.py" --input "$_r2_input" --output "$_r2_output/extraction" "${_r2_source_args[@]}"
_r2_physical_code=0
if [[ ! -e "$_r2_output/physical" ]]; then
    (
        source "$_r2_root/scripts/activate-r1.sh"
        python "$_r2_root/scripts/run-r2-physical.py" --reference "$_r2_output/extraction/sonic-reference.npz" --output "$_r2_output/physical" --video
    ) || _r2_physical_code=$?
fi
if [[ ! -e "$_r2_output/demo" ]]; then
    python "$_r2_root/scripts/render-r2-demo.py" --extraction "$_r2_output/extraction" --physical "$_r2_output/physical" --output "$_r2_output/demo"
fi
python -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); r=json.loads((p/"physical/physical-metrics.json").read_text()); print(json.dumps({"run":str(p),"physical_status":r["status"],"demo":str(p/"demo/comparison.mp4")},indent=2)); sys.exit(0 if r["status"]=="passed" else 1)' "$_r2_output"
exit "$_r2_physical_code"
