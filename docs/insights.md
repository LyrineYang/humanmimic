# What the experiments taught us

[Home](../README.md) / Insights

These notes separate measured observations from design interpretations. They describe the current implementation and its small engineering suite, not universal claims about humanoid control.

## 01 — Staying upright is only one part of imitation

**Observation.** The current R2 suite contains ten physically stable rollouts, but only seven full source passes: three debug and four held-out. The arm-circle debug video passes 3/4 events, stepping passes 0/6, and the last held-out dance passes 5/6. All three remain failed overall. [R2 evidence](../evidence/r2-acceptance-20261101.json)

**Interpretation.** A stability metric alone hides failures of intent, direction and timing. The evaluation should retain separate signals for extraction, physical stability and demonstrated motion events.

**Consequence.** R4 must reach the same target as the original task. Standing still, shrinking away from the target, or rejecting a difficult case must not count as successful adaptation.

## 02 — The clock belongs in the control experiment

**Observation.** The first R1 batch passed 3/10 trials and no motion twice. The recorded simulation advanced at roughly 0.82–0.97 times wall-clock speed. An absolute-deadline pacing repair was followed by three successful diagnostics near real-time speed, then a complete accepted batch with 10/10 passes and joint RMSE of 0.10875–0.17517 rad. [Pacing diagnostics](../evidence/r1-pacing-repair-20261029.json) · [R1 acceptance](../evidence/r1-acceptance-20261029.json)

**Limit.** The first and final batches used different GPU driver versions. The full-batch improvement is not, by itself, a controlled estimate of the pacing change's effect. Each accepted batch must have internally consistent versions; interrupted runs are excluded.

**Consequence.** Record source time, controller-consumed reference indices and simulation time separately. Evaluate matching samples. Do not fit a time shift on test data to make a demonstration look better.

## 03 — Initialization is an input condition

**Observation.** An early stepping rollout fell after consuming 22/574 source references. A fixed initialization diagnostic completed all 574 without falling. The production path now uses 50 hold frames and 100 transition frames at 50 Hz, followed by every unchanged source sample. The five-video initialization regression completed physically, but stepping still failed its event checks. [Experiment history](../EXPERIMENTS.md) · [Initialization implementation](../scripts/r2_initialization.py) · [Debug evidence](../evidence/r2-debug-progress-20261101.json)

**Interpretation.** An abrupt first reference can dominate an otherwise useful motion experiment. Improving initialization does not repair an incorrect extracted gesture.

**Consequence.** Declare initialization once, apply it uniformly, and monitor it for falls. Preserve the original reference and map video time zero to the declared prefix boundary.

## 04 — Memory pressure is also a scheduling problem

**Observation.** The accepted R2 pipeline ran on an RTX 4060 Laptop with 8 GB VRAM by separating extraction stages, persisting caches and releasing perception models before control. Pose inference retains the native FP32, batch-one and flip-augmentation path, with checkpoints every 32 frames. All five held-out videos reached complete extraction and physical execution. [Resource evidence](../evidence/r2-resource-estimate-20261101.json) · [Acceptance](../evidence/r2-acceptance-20261101.json)

**Limit.** Sequential offline success says nothing about running perception and control concurrently at camera rate. The approximately 158-minute held-out queue is a batch duration, not a real-time latency measurement.

**Consequence.** Treat caches as inspectable boundaries. Keep input hashes, versions and stage identities with each cache; recover verified work without silently changing precision or sample coverage.

## 05 — A monocular estimate is not the human's ground truth

**Observation.** The failed held-out dance required a left-knee event above 0.7 rad. The extracted reference reached about 0.48139 rad and the robot about 0.41443 rad. The missing amplitude was already present in the reference. Side convention, monocular depth ambiguity and annotation remain possible explanations; the specific cause has not been isolated. [All outcomes](results.md)

**Interpretation.** Reference-relative tracking error cannot identify every upstream perception error. Conversely, a physical failure does not automatically mean extraction failed.

**Consequence.** Display original footage, estimated 2D/3D motion and actual robot execution together. Label confidence and estimates accurately. Keep source annotations fixed after the held-out run.

## 06 — Geometry is a filter; execution is the question

**Research hypothesis, not a measured result.** A collision-free reference may still be difficult for a frozen controller to track. Some reference edits may be executable even when the unmodified demonstration collides with an obstacle.

The next useful evidence is a pair of counterexamples: a geometrically feasible candidate that fails in closed loop, and an edited candidate that succeeds under the same controller. Neither has been established by this project yet. [R4 experimental design](research.md)

## 07 — Contact is evidence about several possible errors

**Design insight.** A fingertip meeting the object early can mean an incorrect surface, a shifted object, or contact compression. Writing every discrepancy into geometry makes the wrong explanation permanent. Varying load at the same calibrated hand region, with an independent pose constraint, helps distinguish these explanations. Constant load or missing pose evidence may leave them inseparable.

**Implementation and observation.** The CUDA estimator jointly fits pose, local normal displacement and effective compliance, then freezes unobservable directions. An analytic GPU fixture exposed a curvature bias in one-sided tangent-plane residuals; symmetric normal integration reduced the bias without relaxing acceptance thresholds. This verifies a numerical correction on the fixture, not accurate real-object material identification. Pose confidence intervals are still insufficiently calibrated.

**Consequence.** Export evidence, rejected observations and unknown directions with the mesh. Never use simulator contact locations as estimator inputs. [Mechanism and limitations](r4-multimodal.zh-CN.md#04-接触怎样修正几何而不把错误写进网格)

## 08 — Memory should retain evidence without manufacturing confidence

**Design insight.** A newly occluded groove should not disappear from the object model, but an old object pose should not remain certain after a slip. Persistent shape, changing pose and confidence have different lifetimes.

**Implementation.** Explicit memory stores unique timestamped visual/tactile/action evidence and an object-coordinate belief. It selects a bounded mix of recent and older observations. Cached poses initialize a solve; the old posterior is not treated as another independent sensor. This is an inspectable baseline, not an implemented learned WSM. The M1 comparison must hold window size, point count and optimization budget fixed to test whether selecting useful history actually helps. [Memory design](r4-multimodal.zh-CN.md#03-多模态记忆到底怎样实现)

## 09 — More touch does not establish a geometry contribution

**Research hypothesis.** Improving the geometry used for control should reduce manipulation error beyond what direct force feedback already achieves. E2 therefore compares all four geometry/force combinations with common references, gains, safety limits and independent executions. Its primary contrast is G1F1 versus G0F1; failures remain in the denominator.

**Research hypothesis.** A useful probe should reduce task-relevant uncertainty, not simply global uncertainty. E3 compares no probe, random, uniform, global-information and task-sensitive selection under the same budget. Current task sensitivities are explicit grasp/support surrogates; they are not gradients of actual task success. The default implementation abstains when its force-prediction bound lacks calibration. Neither hypothesis has yet been demonstrated by successful grasp/place trials. [Experimental design](r4-multimodal.zh-CN.md#07-每组实验到底回答什么产出什么)

## What these notes do not establish

The current evidence does not establish unseen-task generalization, real-time camera operation, real-robot transfer, obstacle avoidance, or a new learning algorithm. The original five R2 held-out videos are now used data. Subsequent method changes need a new frozen test split.
