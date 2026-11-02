#!/usr/bin/env python3
"""Separate private evaluator; never invoke from the public estimator worker."""
import argparse
import json
from pathlib import Path
import numpy as np
from r4_belief_evaluation import evaluate_beliefs
from r4_contract import sha256, write_json
from r4_cuda import require_cuda
from r4_public import validate_prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["belief", "prior", "evaluation-scene", "actual-state", "output"]:
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    device, gpu = require_cuda()
    prior = validate_prior(json.loads(args.prior.read_text()))
    with np.load(args.actual_state, allow_pickle=False) as archive:
        actual = archive["samples"]  # I/O only; numeric evaluation runs on CUDA.
    metrics = evaluate_beliefs(json.loads(args.belief.read_text()), prior, json.loads(args.evaluation_scene.read_text()), actual, device)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/"metrics.json", metrics)
    write_json(args.output/"manifest.json", {"status": "complete", "gpu": gpu, "heldout_used": False,
        "source_sha256": sha256(Path(__file__).with_name("r4_belief_evaluation.py")),
        "inputs_sha256": {name: sha256(getattr(args, name)) for name in ["belief", "prior", "evaluation_scene", "actual_state"]}})


if __name__ == "__main__":
    main()
