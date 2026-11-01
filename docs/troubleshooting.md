# Troubleshooting

[Home](../README.md) / Help · [Setup](getting-started.md) · [Usage](usage.md)

Start with the command's message and the relevant stage log. A missing dependency, an unfinished run, a failed motion event and a physical fall require different fixes.

## Setup and input

| Symptom | What it means | Next step |
| :--- | :--- | :--- |
| `Project Miniforge is missing` or `R2 environment missing` | Source was cloned, but the required environment is absent. | Follow the [runtime checklist](getting-started.md#prepare-a-runtime). Activation scripts do not install packages. |
| `Unrecognized R2 storage root` | The selected volume has not been prepared and verified for this project. | Confirm the intended data volume and migration configuration. Do not create a dummy ownership marker to skip validation. |
| `Host disk reserve below configured floor` | The configured C/D free-space floor was not met. | Inspect capacity and choose an appropriate storage layout. Preserve prior results and models. |
| `Local machine rebooted: user requested server handoff, not more local retries` | The boot identity changed and the source-machine execution policy blocks more local work. | Follow [HANDOFF.md](../HANDOFF.md). This also applies to `--check-only`; changing the run ID does not clear it. |
| Input or annotation path rejected | A file is missing, or the annotation does not match the input SHA/role. | Use an absolute existing path. Bind your own source hash and `debug` annotation role. |
| Reserved held-out source | The video belongs to a declared held-out suite. | Use its frozen suite workflow. All five original held-out videos are already used; do not reclassify them as unseen. |
| Unsupported source duration | The current video path accepts complete sources up to 60 seconds. | Choose an appropriate complete input; the pipeline does not silently trim it. |

## During execution

| Symptom | What to inspect | How to proceed |
| :--- | :--- | :--- |
| Another pipeline is active | Reported PID, task identity, boot/start time and latest invocation log | Follow the existing run; do not start a duplicate because an observation timed out. |
| No visible progress for a while | Stage-specific `*-invocation-*.log`, extraction attempt logs and checkpoints | Distinguish loading, active work and an exited process. Offline extraction is slower than clip playback. |
| Existing terminal result is returned | `cached_result_only` or `previous_terminal_run_preserved` | Read the retained result. Use a new ID only for an intentionally new attempt on a ready target. |
| Pipeline ended before a report exists | Most recent invocation log and extraction error records | Early failures can occur before report generation. Keep the original evidence while identifying the failed dependency/stage. |
| Native controller cannot load a library | R1 activation, native library paths and matched SDK/DDS versions | Verify the native runtime; a successful Python import does not prove C++ controller readiness. |
| Server differs from the original GPU/paths | Target compatibility, storage checks and runtime identity | Complete migration and new-target verification. Prior 4060 results do not certify another GPU. |

## The demo exists, but the result is not passed

**Missing event annotations:** exploration may generate a full comparison while keeping body/event acceptance `awaiting_verification`. Predeclare events for a new measured run; do not derive pass thresholds from a result you already inspected.

**Visual review pending:** media decoding can pass while final visual review remains incomplete. Review the full comparison, including beginning/middle/end and failure moments; bind the completed review to the exact comparison SHA. Do not automatically mark it passed just because the MP4 opens.

**Stable robot, failed gesture:** inspect `body-audit/body-evaluation.json` and compare source footage, reference and actual motion. The existing suite includes stable rollouts that missed event amplitude or direction. Keep their failed status.

**Robot fell or execution stopped:** inspect `physical/physical-metrics.json` and the actual state/logs. A full-length comparison can include a clearly marked stopped-execution interval; it does not imply a complete physical rollout.

[Status and exit-code details](usage.md#status-and-exit-codes) · [Known suite failures](results.md#failures-remain-part-of-the-result)

## Interrupted runs

1. Check whether the recorded process is still alive using both its identity and current logs; a historical `running` label is insufficient.
2. Preserve the partial directory, failure record and source/configuration/model identities.
3. Identify whether interruption occurred in extraction, physical execution or rendering. Cache reuse, controller reruns and video regeneration are different operations.
4. Select the matching recovery path from the current execution plan. The existing `resume-r2-demo.py` is a legacy preflight tool with machine-specific checks, not a general installer or retry wrapper.
5. If physical execution already failed, keep that trial. Any new physical attempt needs a new identity and comparable configuration.

The original workstation is paused for Linux migration. Keep its evidence and continue preparation on the intended target rather than weakening the source-machine boot guard.

## What to include in a bug report

Provide the Git commit, OS/GPU/runtime versions, exact command with private paths redacted as needed, expected behavior, observed behavior, run ID and the smallest relevant log excerpt. State whether this was new extraction, cached reuse, a fresh physical trial or rendering only. Link the relevant metrics without uploading credentials, licensed body assets or full private videos.

[Contribution guide](../CONTRIBUTING.md) · [Issue tracker](https://github.com/LyrineYang/humanmimic/issues)
