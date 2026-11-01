# Usage

[Home](../README.md) / Usage · [Setup](getting-started.md) · [Troubleshooting](troubleshooting.md)

The recipes below assume a prepared, authorized execution target. **The original workstation is currently paused for server migration**; these are usage instructions, not a request to restart it. For a new machine, complete the [runtime checklist](getting-started.md#prepare-a-runtime) first.

## Video to simulation

### Choose an input

Use a local video file up to 60 seconds: one person, fixed camera, whole body and feet visible, level floor. A simple gesture or squat is a useful first input. The runner does not download a URL; `--source-url` records provenance for an existing local file.

### Inspect before running

Run commands from the repository root. Replace the input path and pick a new run ID for a new attempt:

```bash
source scripts/activate-r2.sh
python scripts/run-r2-video.py \
  --input /absolute/path/to/clip.mp4 \
  --run-id my-first-video \
  --check-only
```

The check does not invoke perception or control. It still requires valid storage and execution-policy configuration, and it does not prove that models or the controller will run.

| Report field | What to do |
| :--- | :--- |
| `output` | Note the directory where this run would be written. |
| `active_task_pids` | Continue only when empty; otherwise inspect the existing task and logs. |
| `reserved_heldout_source` | If `true`, use the frozen suite workflow; do not submit it as a new debug video. |
| `cached_terminal_result_available` | If `true`, the run has a retained result; another call will report it rather than perform a new trial. |
| `event_annotation_provided` | `false` is fine for exploration; full motion-event acceptance requires annotations. |

A top-level `status: passed` in this inspection means the check completed. It can still report active tasks or a reserved source; read the fields above before proceeding.

### Execute

When the inspection is clear, run the same command without `--check-only`:

```bash
python scripts/run-r2-video.py \
  --input /absolute/path/to/clip.mp4 \
  --run-id my-first-video
```

This runs extraction, reference conversion, the matched R1 controller/simulator, evaluation and comparison rendering in sequence. It preserves stage logs and data as it goes. Existing failed physical trials are not automatically replaced.

### Options

| Option | Purpose |
| :--- | :--- |
| `--input PATH` | Required local video path. |
| `--run-id NAME` | Required output name; start with a letter/digit, then use letters, digits, `.`, `_` or `-`. |
| `--source-url URL` | Optional original source address for provenance; not a downloader. |
| `--events PATH` | Optional source-based event annotations for measured imitation checks. |
| `--check-only` | Input, storage and scheduling inspection; no model or controller execution. |

## Find and interpret the output

Read the final JSON printed by the command for `run`, `demo` and `status`. The default root is `/mnt/d/humanoid-demo-r2/runs/`; `R2_STORAGE_ROOT` selects the configured data root.

| Path within the run | Use it to… |
| :--- | :--- |
| `REPORT.md` | Read the outcome and links to available artifacts. Created when the audit has sufficient results. |
| `demo/comparison.mp4` | Compare the original, estimated motion and recorded robot execution over the full source timeline. |
| `demo/demo.json` | Inspect frame coverage and comparison metadata. |
| `extraction/source-original.mp4` | Return to the actual input. |
| `extraction/sonic-reference.npz` | Inspect the converted reference sent toward control. |
| `physical/actual-state.npz` | Inspect recorded physical execution. |
| `physical/physical-metrics.json` | Check physical stability and source consumption. |
| `body-audit/body-evaluation.json` | Check body tracking, event direction/order and timing. |
| `*-invocation-*.log` | Diagnose a failed or unfinished stage. |
| `run-audit*.json` | Read the stage/acceptance audit, including unresolved visual review. |

An early failure may not produce a report or demo; inspect its invocation logs first. Some recovered runs have an `artifact-layout.json` mapping to alternate directories—use it and the command's returned paths instead of assuming the default layout.

### Status and exit codes

| Status | Meaning | Normal completed-run exit |
| :--- | :--- | :--- |
| `passed` | Required extraction, physics, event and media/visual checks passed. | `0` |
| `failed` | At least one required check failed; the evidence is retained. | `1` |
| `awaiting_verification` | Work or review is incomplete, including missing event annotations or visual review. | `2` |

Argument errors also use exit `2`, and runtime exceptions can exit `1`. **Read the JSON/log message, not just the exit code.** Inspection mode can exit `0` without performing a trial.

A generated MP4 is not an acceptance badge. Its robot panel is offline playback of recorded actual states; the human 3D panel is an estimate, not ground truth. A stable robot may still miss the demonstrated gesture.

## Add motion-event evaluation

For an evaluated attempt, define events from the source video **before** inspecting that attempt's outcome. Start from the [existing annotation example](../configs/r2-debug-events-QqvZAUEOrAQ.json), adapting the events to your own source rather than copying another video's labels.

- Bind `source_sha256` to the original file, and set `role` to `debug` for a single-video run.
- Give events unique IDs and increasing `source_event_seconds`.
- Predeclare event descriptors, thresholds, windows and direction/ordering expectations.
- Save the file and use it for a new run with `--events /absolute/path/to/events.json`.

The descriptor implementation is in [evaluate-r2-body.py](../scripts/evaluate-r2-body.py). Full acceptance also needs visual inspection bound to the final comparison's SHA. The runner does not automatically sign off that review.

To produce a new derived audit after the required annotations and review are present:

```bash
source scripts/activate-r2.sh
python scripts/audit-r2-run.py \
  --run /absolute/path/to/existing-run \
  --output /absolute/path/to/existing-run/run-audit-review-01.json
```

Choose a new audit filename within the configured data root. This checks saved artifacts and can regenerate the report, preserving its previous version; it does not launch a new controller trial or change a failed physical result.

## Reference motion to simulation

This exercises the G1 controller path without video perception, using the configured default reference. It still needs the complete R1 runtime and assets:

```bash
source scripts/activate-r1.sh
python scripts/run-r1-reproduction.py --output runs/reference-demo-NEW
python scripts/summarize-r1.py --run runs/reference-demo-NEW
```

This is one run, not the full five-motion, two-trial suite. See [r1-suite.json](../configs/r1-suite.json) for the accepted motion list and [results](results.md) for the existing evidence. A different environment needs new verification.

## Inspect an existing run or continue interrupted work

Opening existing reports, JSON metrics and MP4s does not require rerunning inference. Recorded-state playback and cached extraction reuse are different from a new extraction/physical trial; label them accordingly.

Before attempting recovery, establish which process and stage stopped, compare source/configuration/cache identities, and preserve the earlier attempt. Read [Interrupted runs](troubleshooting.md#interrupted-runs) before selecting a recovery command. The legacy resume tool is not a universal one-command retry, and the current source workstation must follow the server-migration decision.
