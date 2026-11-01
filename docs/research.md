# Adapting motion with limited physical verification

[Home](../README.md) / Research direction

**Status: proposed, not implemented.** R1 and R2 provide the execution and measurement infrastructure. R4 will investigate whether a small, explicitly bounded amount of closed-loop evaluation can make scene-constrained motion edits more reliable.

## The question

Given a demonstration, a target and a known obstacle, how should a system spend a fixed compute budget to find a reference motion that a frozen humanoid controller can execute?

This project focuses on reference adaptation and verification. It reuses pretrained SONIC weights. Adding scene information alone is not a claim of novelty; the contribution would need to come from measured behavior, a clear baseline and a defensible budget comparison.

## The first setting

Use a mostly stationary, two-foot-supported, single-arm reach around one static box in simulation. Obstacle geometry is known. Keep the robot, original motion, target, policy weights, initialization and evaluation rules fixed across methods. Modify the reference; never write a candidate directly into the robot's actual state during execution.

Starting with known geometry removes scene reconstruction as a confound. Restricting the task makes the gap between geometric feasibility and controller execution testable before expanding to walking or contact-rich tasks.

## Two decisive experiments

| Experiment | Required evidence | If it fails |
| :--- | :--- | :--- |
| **Geometry is insufficient** | At least one candidate passes the declared kinematic/collision checks but fails actual SONIC + MuJoCo execution | Re-examine the task and baselines before claiming a need for learned execution risk |
| **Reference adaptation is usable** | At least one edited reference reaches the original target, avoids the box and remains stable under frozen SONIC | Fix the candidate representation or execution interface before scaling search |

These are research decision points, not replacements for R4's full acceptance criteria.

## Proposed method

1. Parameterize a small number of wrist-path control points around the original reach.
2. Generate bounded perturbations while preserving the endpoint and motion identity.
3. Use inverse kinematics, joint limits and collision distances to reject invalid candidates cheaply.
4. Evaluate a fixed maximum number of survivors using the real frozen controller and MuJoCo.
5. Select a candidate that satisfies task, collision and stability constraints; rank valid candidates by deviation and compute cost.
6. If none succeeds, report rejection or failure explicitly. Do not silently relabel it as a safe success.

The first implementation should use deterministic search with recorded seeds. A small execution-risk predictor or adaptive allocation of rollout budget is a later hypothesis, conditional on the two experiments above and enough properly separated data. It is not required to claim completion of the existing R4 plan.

## Comparisons

| Method | Purpose |
| :--- | :--- |
| Unmodified demonstration | Establish the scene-induced failure |
| Amplitude scaling | Test a simple, inexpensive alternative |
| Geometric edit without closed-loop selection | Isolate the value of execution checks |
| Full edit + bounded closed-loop selection | Test the proposed R4 method |

Use the same layouts and targets for all methods. Report actual simulation calls and wall time, including unsuccessful candidates. Future adaptive-budget methods must be compared with a fixed-budget search at matched resources.

## Evaluation, fixed before testing

The authoritative criteria remain in [PLAN.md](../PLAN.md). Develop on **10 layouts**, then freeze **at least 20 separate layouts** with seeds and geometric/task definitions. Record any test use; after inspecting results, those layouts are no longer unseen.

R4 passes only if at least **three held-out layouts** show the original motion colliding while the adapted motion reaches the **same target**, avoids collision and remains stable in actual physical execution. Deliver at least three complete comparison recordings and report every layout, including failures.

Report task success rate, collision rate, stability, motion deviation and computation time. Also retain planning calls, rollout count, memory and rejection/degradation rates to support later budget comparisons. A method that declines the hard cases has not solved them.

## Scope and dependencies

R1 provides a verified physical execution path; R2 adds full video provenance and event evaluation. R3 still needs a real camera and concurrency/latency measurements. R4 can begin independently of camera availability using accepted references.

The reported availability of four V100 32 GB cards is future capacity, not an established execution result. Their host, software compatibility and storage have not been accepted. The verified results here remain from the 4060. No distributed run, new model training or paid deployment is implied by this design.

Contact-rich tasks, scene reconstruction from video, controller distillation, world-model acceleration and full foundation-policy training are deferred. A related-work review must precede any novelty claim; this document describes a testable project direction rather than a publication claim.
