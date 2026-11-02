# From video geometry to dexterous interaction

[Home](../README.md) / Research direction

**Status: development code and bounded V100 checks available; manipulation benefit unverified. Updated 2026-11-02.** R4 is now the main research direction; on-site camera R3 is skipped for this stage. The accepted R1/R2 results remain tied to the original workstation.

## The question

At a fixed observation and compute budget, can task-relevant local geometry and explicit uncertainty improve dexterous manipulation accuracy and success more than uniformly refining an object's reconstruction?

The proposed pipeline separates scene context, dynamic object shape/pose, hand contact phases, retargeting and physical execution. Planning receives reconstructed geometry; evaluation uses independently known geometry. This separation matters: evaluating against the same incorrect mesh can conceal scale errors, penetration and missing functional details.

## What the review changes

VideoMimic informs global human/scene reconstruction; WM-Craftnet informs recurrent visual/tactile state estimation. More direct video-to-hand-object-to-robot methods already exist, including VideoManip, Do as I Do, C2Dex and OmniHOI. Combining reconstruction, contact constraints and retargeting alone is not a novelty claim.

Candidate contributions are budgeted task-sensitive refinement, robustness across plausible geometry hypotheses, and evidence that geometric improvements cause better execution. Compare these against uniform refinement, contact-only refinement and uncertainty-only selection with the same inputs and controller. Keep shape, pose and controller improvements separate in ablations.

[Detailed Chinese research report, sources and evaluation design](research-video-interaction.zh-CN.md) · [Observed server readiness and migration gaps](server-readiness.zh-CN.md)

## Scope and evidence

The independently prepared V100 runtime now supports LEAP/MuJoCo collection, NVIDIA EGL rendering and CUDA estimation. The user has authorized local implementation, environment preparation and bounded development checks. Training from scratch, paid resources, real hardware and the formal held-out cohort remain outside this round. MuJoCo dynamics run on the CPU; estimation, planning numerics and rendering use the GPU. No CPU estimator fallback is provided.

The implementation now includes a four-finger force bridge, a public-observation/private-evaluation boundary, joint shape/pose/effective-compliance estimation, persistent evidence memory, bounded reference corrections and task-sensitive probe selection. These are development components. Successful manipulation and a causal gain from geometry refinement have not been established. The complete VideoManip frontend and a learned WSM runtime are also not ready.

## The current research loop

Maintain an object-coordinate model and its uncertain pose; retain unique visual, tactile and action evidence; use new contact observations to distinguish shape error from motion or contact compression; then spend the next observation on a region whose uncertainty matters to the task. Finally, measure actual execution in a separate physical world. A better-looking mesh is not the endpoint.

Memory currently means explicit evidence and belief storage, not a trained latent state: at most 32 keyframes, with at most eight selected per update. Previous posteriors initialize the next solve; they are not counted again as independent measurements. Missing observations grow uncertainty. Shape/pose/compliance ambiguities remain marked unknown.

The decisive control is a four-way geometry/force-feedback comparison: G0F0, G1F0, G0F1 and G1F1. G1F1 versus G0F1 asks whether geometry helps after direct force feedback is already available. E1 tests perception on the same recordings; M1 tests recent versus persistent evidence; E3 compares probe strategies under equal contact/time/force limits. E4/E5 separately investigate learned memory and any later authorized training.

VideoManip already includes contact optimization. Our proposed addition is an inspectable feedback and evaluation loop around uncertain geometry during execution, complementary to video-derived demonstrations. We do not claim to reproduce its unpublished training pipeline or outperform it on incomparable tasks. See the [plain-language walkthrough, comparison and experimental matrix](r4-multimodal.zh-CN.md#0-先读这一节推进什么为什么以及交付什么) and [implementation/run guide](r4-multimodal.zh-CN.md#10-当前实现环境与运行入口).

Before future execution, freeze the task family, hand embodiment, input modalities, tolerances, budget and held-out split after development. Report local surface/normal error, scale and pose, actual task accuracy, success, slips, penetration, rejection and total cost. All original R2 held-out videos are already used.

## Preserved known-geometry baseline

The previous R4 design used a mostly stationary single-arm reach around one known static box, editing reference motion under frozen SONIC. Its original comparison remains: original motion, amplitude scaling, geometric editing without closed-loop selection, and full editing with bounded physical evaluation.

Its original acceptance remains archived in [PLAN](../PLAN.md#r4-场景约束动作修正): 10 development layouts, at least 20 held-out layouts, and at least three cases where adaptation avoids the original collision while stably reaching the same target, with complete comparison recordings. These criteria have not been weakened. This is now an optional baseline; completing it would not establish the expanded R4 research objective.

The authoritative current scope and next steps are in [PLAN](../PLAN.md); operational context is in [HANDOFF](../HANDOFF.md).
