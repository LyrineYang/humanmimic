# Usage

[Home](../README.md) / Usage · [Setup](getting-started.md) · [Troubleshooting](troubleshooting.md)

The recipes below assume a prepared, authorized execution target. **The original workstation is currently paused for server migration**; these are usage instructions, not a request to restart it. For a new machine, complete the [runtime checklist](getting-started.md#prepare-a-runtime) first.

## CUDA example and results

After [setup](getting-started.md#prepare-a-runtime), run the generated fixture with an explicitly selected GPU:

```bash
python scripts/humanmimic.py example --gpu GPU-... --output runs/my-first-example
python3 scripts/humanmimic.py inspect runs/my-first-example
# Strict research acceptance check of the SAME saved result; no rerun:
python3 scripts/humanmimic.py inspect runs/my-first-example --require-acceptance
```

The last command exits 3 while research acceptance remains unverified. The normal run exits 0 after successful artifact generation. Read `task_status` for the analytic engineering thresholds and `acceptance_status` for the separate research conclusion. A generated fixture does not establish manipulation gains.

| Artifact | Meaning |
| --- | --- |
| `REPORT.md` / `comparison.svg` | Explanation and object-local coarse/estimated surface illustration |
| `public-observations/` | Generated visual/contact observations and coarse prior |
| `estimation/belief.json` | Separate CUDA worker's estimated state and uncertainty |
| `private-evaluation/` | Analytic labels/metrics withheld from the estimator |
| `manifest.json` / `result.json` | Source/configuration/GPU identity, results and status contract |

The example uses no private assets, no CPU numerical fallback, no policy training and no physical rollout. Use a fresh output directory for each run; existing evidence is never overwritten.

## Video to simulation

### Choose an input

Use a local video file up to 60 seconds: one person, fixed camera, whole body and feet visible, level floor. A simple gesture or squat is a useful first input. The runner does not download a URL; `--source-url` records provenance for an existing local file.

### Inspect before running

Run commands from the repository root. Replace the input path and pick a new run ID for a new attempt:

```bash
python scripts/run-r2-video.py \
  --target r4-v100 \
  --input /absolute/path/to/clip.mp4 \
  --run-id my-first-video \
  --check-only
```

Use Python 3.10+ for this existing R2 entry (the R4 Python also suffices for inspection). The check does not invoke perception or control. It reports target authorization, dependencies and disk reserves without bypassing original-machine protection. It inspects file identity, not video decoding or model readiness.

| Report field | What to do |
| :--- | :--- |
| `output` | Note the directory where this run would be written. |
| `active_task_pids` | Continue only when empty; otherwise inspect the existing task and logs. |
| `reserved_heldout_source` | If `true`, use the frozen suite workflow; do not submit it as a new debug video. |
| `cached_terminal_result_available` | If `true`, the run has a retained result; another call will report it rather than perform a new trial. |
| `event_annotation_provided` | `false` is fine for exploration; full motion-event acceptance requires annotations. |

`execution_status: completed` means inspection completed. `ready_to_attempt`, `authorization` and `issues` describe the separate target readiness. The Linux R4 profile reports R2 as diagnostic-only; do not remove `--check-only` until a full R2 runtime and execution target have been authorized and verified.

### Execute

On a separately prepared and authorized R2 target, activate its R2 environment and use the matching profile. For the historical target (still paused by its boot policy):

```bash
source scripts/activate-r2.sh
python scripts/run-r2-video.py \
  --target legacy-wsl \
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
| `--check-only` | Input, target and scheduling inspection; no model or controller execution. |
| `--target NAME_OR_JSON` | Independent target paths, reserves and execution policy; defaults to legacy-wsl. |
| `--require-acceptance` | Strict exit status using unchanged research acceptance. |

## Find and interpret the output

Read the final JSON printed by the command for `run`, `demo`, `execution_status`, `task_status`, `review_status` and `acceptance_status`. The default root is `/mnt/d/humanoid-demo-r2/runs/`; `R2_STORAGE_ROOT` selects the configured data root.

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

| Field | Meaning |
| --- | --- |
| `execution_status` | `completed`: the audit verified generated extraction/media; `incomplete`/`failed`: command did not produce a complete verified artifact package |
| `task_status` | Physical/event or analytic task checks: `passed`, `failed`, or `awaiting_verification` |
| `review_status` | Pending or completed review; no automatic visual sign-off |
| `acceptance_status` | Original strict research decision, unchanged by successful artifact generation |

Normal exploration exits **0** for completed execution and **1** for failed/incomplete execution. Inspect task/acceptance fields even on exit 0. `--require-acceptance` instead returns **0** only for accepted results, **1** for failed execution/acceptance, and **3** for missing research evidence. Argument errors use **2**. The existing strict suite/audit entry points retain their original acceptance and exit conventions; this change does not turn a failed gesture or fall into a pass.

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
