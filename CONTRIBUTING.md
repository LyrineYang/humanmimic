# Contributing

[Home](README.md) / Contributing

HumanMimic welcomes practical improvements and carefully scoped exploration. Useful starting points include clearer setup instructions, better error messages, portability fixes, easier inspection of saved runs and experiments that test a concrete hypothesis.

This is currently a private repository. The project has not selected an open-source license; third-party assets keep their own terms.

## Report a problem

Check [troubleshooting](docs/troubleshooting.md), then [open an issue](https://github.com/LyrineYang/humanmimic/issues) with:

- The expected result and what happened instead.
- The Git commit, target environment and exact command.
- Whether the attempt used a fresh input, cached extraction, a new physical rollout or recorded-state rendering.
- A small relevant log excerpt and the applicable status/metric fields.

Keep credentials, restricted models and full private recordings out of issue attachments. The [usage guide](docs/usage.md#find-and-interpret-the-output) maps each artifact to its purpose.

## Propose a change

Keep the problem and intended behavior small enough to review. For a usability fix, show the command or reader path it improves. For a runtime change, state the testable expectation before running it and record the versions/configuration used.

Use a separate branch and preserve unrelated work. Check links/rendering for documentation changes; rerun the affected environment or physical checks for runtime changes. A source-level check does not substitute for target-hardware acceptance.

A useful pull-request description answers: what behavior changes, why, how it was checked, and what remains unverified. Include before/after evidence when available. No change should require a reviewer to reconstruct the conversation that led to it.

## Routine checks

Use the supported R4 environment and a new result directory per invocation:

```bash
source scripts/activate-r4-research.sh
make doctor
make check RUN_ID=my-change-contracts
# After checking occupancy and exporting one CUDA_VISIBLE_DEVICES UUID:
make check-gpu RUN_ID=my-change-gpu
```

`check` parses source/shell and exercises package-isolation, target-diagnosis and status contracts. It performs no estimator numerical test. `check-gpu` runs the review regressions and full P2 suite on CUDA. It does not launch held-out tests, training, paid resources or a physical manipulation trial. Existing CPU research prototype tests are separate historical tools and are not silently included.

For installer changes, rebuild into a genuinely empty prefix with `humanmimic.py bootstrap`, then run the generated example from a clean checkout of the proposed commit. Keep archive/lock hashes, the install manifest, hardware identity, all failure logs and the new output report. A working existing environment is not fresh-install evidence. Native-controller or physics changes need their own target checks; a green CLI contract suite is insufficient.

## Explore an idea

Start with a question and a comparison, not an improved headline number. The [insights](docs/insights.md) summarize observed failure modes; the [research design](docs/research.md) describes the current video-geometry and dexterous-interaction questions.

Predeclare the inputs, metric, control and compute budget. Keep development and held-out data separate. The original five R2 held-out videos have all been used; they cannot become unseen tests again. Preserve failed candidates and distinguish physical stability, imitation correctness and task success.

Use the same hardware, motions, weights and evaluation rules for controlled comparisons, or explicitly report the confound. Do not tune thresholds on test outcomes, replace actual states with references, or count rejection of a task as successful execution.

## Project records

[PLAN.md](PLAN.md) holds current acceptance and next steps; [EXPERIMENTS.md](EXPERIMENTS.md) preserves historical evidence. Add meaningful results there and keep raw logs in ignored `runs/<run_id>/` directories. [AGENTS.md](AGENTS.md) defines repository execution rules; [HANDOFF.md](HANDOFF.md) covers the current server-migration boundary.
