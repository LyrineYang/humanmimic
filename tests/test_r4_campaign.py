"""Standard-library resource/manifest tests only; no CPU research computation."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from r4_campaign import Ledger, assert_frozen, digest, exclusive, idle_device, read, stop_group, validate_limits

spec = importlib.util.spec_from_file_location("campaign_runner", ROOT/"scripts/run-r4-campaign.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"ledger.json"
        self.limits = copy.deepcopy(read(ROOT/"configs/budget.json")["local_r4_campaign"])
        self.clock = 1000.
        self.monotonic = 100.
        self.ledger = self.reopen()

    def reopen(self):
        return Ledger(self.path, self.limits, now=lambda: self.clock, monotonic=lambda: self.monotonic, boot="fixture")

    def reserve(self, key="a", gpu="GPU-0", seconds=430, stage="E3"):
        self.ledger.reserve(key, stage, gpu, seconds, "fixture-sha")

    def test_not_started_by_preparation(self):
        self.assertIsNone(self.ledger.state["start_epoch"])
        self.assertFalse(self.path.exists())

    def test_actual_failure_cost_not_full_reservation(self):
        self.reserve()
        self.monotonic += 31
        self.ledger.finish("a", {"execution_status": "failed"})
        self.assertEqual(self.ledger.committed(), 31)
        self.assertEqual(self.reopen().committed(), 31)

    def test_restart_does_not_reset_wall_clock(self):
        self.reserve(); self.ledger.finish("a", {})
        self.clock += 36*3600-400; self.monotonic += 36*3600-400
        self.ledger = self.reopen()
        with self.assertRaisesRegex(RuntimeError, "wall-clock"):
            self.reserve("b")

    def test_clock_rollback_cannot_extend_session(self):
        self.reserve(); self.ledger.finish("a", {})
        self.clock -= 100000; self.monotonic += 36*3600
        with self.assertRaisesRegex(RuntimeError, "wall-clock"):
            self.reserve("b")

    def test_duplicate_and_same_gpu_rejected(self):
        self.reserve()
        with self.assertRaises(RuntimeError): self.reserve()
        with self.assertRaises(RuntimeError): self.reserve("b")
        self.assertEqual(len(self.ledger.state["jobs"]), 1)

    def test_four_slot_limit(self):
        for i in range(4): self.reserve(str(i), "GPU-"+str(i))
        with self.assertRaisesRegex(RuntimeError, "concurrency"):
            self.reserve("fifth", "GPU-4")

    def test_stage_reservation_includes_all_active_jobs(self):
        self.limits["stage_gpu_hours"]["E3"] = .2
        self.reserve(seconds=430)
        with self.assertRaisesRegex(RuntimeError, "Stage"):
            self.reserve("b", "GPU-1", seconds=430)

    def test_total_limit_includes_other_stages(self):
        self.ledger.state["jobs"]["historic"] = {"stage": "prerequisites", "status": "finished", "charged_s": 144*3600-100, "reserved_s": 10}
        with self.assertRaisesRegex(RuntimeError, "Total"):
            self.reserve(seconds=430)

    def test_overrun_is_not_clipped(self):
        self.reserve(seconds=5); self.monotonic += 8; self.ledger.finish("a", {})
        self.assertEqual(self.ledger.committed(), 8)

    def test_busy_gpu_refused_even_with_free_memory(self):
        devices = {"GPU-x": {"name": "Tesla V100", "free_mib": 28000, "compute_pids": [123]}}
        with self.assertRaisesRegex(RuntimeError, "unavailable"): idle_device(devices, "GPU-x")
        devices["GPU-x"]["compute_pids"] = []
        self.assertEqual(idle_device(devices, "GPU-x")["free_mib"], 28000)

    def test_nonfinite_and_unauthorized_budgets_rejected(self):
        for key, value in [("gpu_hours_max", 145), ("wall_hours_max", float("nan")), ("training", True), ("paid_usd", 1)]:
            limits = copy.deepcopy(self.limits); limits[key] = value
            with self.assertRaises(ValueError): validate_limits(limits)

    def test_exclusive_coordinator_lock(self):
        first = exclusive(Path(self.tmp.name)/"coordinator.lock")
        try:
            with self.assertRaisesRegex(RuntimeError, "Another campaign"):
                exclusive(Path(self.tmp.name)/"coordinator.lock")
        finally:
            first.close()

    def test_private_group_cleanup(self):
        # Tiny sleeping stdlib children only; no GPU or simulation.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        try:
            stop_group(child)
            self.assertIsNotNone(child.poll())
            stop_group(child)  # leader already gone: cleanup remains idempotent
        finally:
            if child.poll() is None: child.kill(); child.wait()

    def test_matrix_size_pairing_and_balance(self):
        cfg = read(ROOT/"configs/r4-e3-campaign.json")
        rows = runner.matrix(cfg)
        counts = {s: sum(r["stage"] == s for r in rows) for s in ["E1", "E2", "E3"]}
        self.assertEqual(counts, {"E1": 72, "E2": 144, "E3": 504})
        self.assertEqual(sum(r["stage"] == "E3" and r["variant"] == "core" for r in rows), 360)
        self.assertEqual(len({r["id"] for r in rows}), 720)
        pairs = {}
        for r in rows:
            if r["stage"] == "E1": continue
            key = (r["object_id"], r["seed"], r["task"])
            pairs.setdefault(key, set()).add(r["slot"])
        self.assertTrue(all(len(slots) == 1 for slots in pairs.values()))
        hours = [sum(r["timeout_s"] for r in rows if r["slot"] == slot)/3600 for slot in range(4)]
        self.assertEqual(hours, [22.1]*4)
        self.assertLessEqual(max(hours)+8, 36)

    def test_missing_or_negative_gates_not_bypassable(self):
        path = Path(self.tmp.name)/"gates.json"
        path.write_text(json.dumps({"successful_baselines": [], "leap_calibration_report": "missing"}))
        with self.assertRaisesRegex(ValueError, "successful fixed references"):
            runner.gate_files(path, [{"object_id": "stepped_prism-101", "task": "lift_hold"}])

    def test_dispatch_and_resume_do_not_repeat_finished_jobs(self):
        # Exercise real subprocess launch/watchdog/ledger without scientific work.
        root = Path(self.tmp.name)
        (root/"scripts").mkdir()
        fixture = root/"scripts/fixture.py"
        fixture.write_text("import json,sys\nfrom pathlib import Path\np=Path(sys.argv[1]); p.mkdir(); (p/'result.json').write_text(json.dumps({'status':'passed','scope':'stdlib fixture only'}))\n")
        gpu = {"uuid": "GPU-fixture", "name": "V100 fixture", "index": 0, "driver": "fixture", "free_mib": 32000, "compute_pids": []}
        cfg = {"campaign_id": self.limits["campaign_id"]}
        plan = {"campaign_id": cfg["campaign_id"], "python": sys.executable, "environment_prefix": sys.prefix,
                "gpus": {gpu["uuid"]: gpu}, "frozen_sha256": {}, "jobs": [], "data_root": str(root)}
        for i in range(2):
            output = root/("fixture-output-"+str(i))
            plan["jobs"].append({"id": str(i), "stage": "prerequisites", "gpu_uuid": gpu["uuid"], "timeout_s": 10,
                                "output": str(output), "argv": ["fixture.py", str(output)]})
        path = root/"plan.json"; path.write_text(json.dumps(plan))
        args = SimpleNamespace(plan=path, storage_review=None)
        usage = SimpleNamespace(free=1000*1024**3)
        with patch.object(runner, "ROOT", root), patch.object(runner, "inventory", return_value={gpu["uuid"]: gpu}), \
                patch.object(runner.shutil, "disk_usage", return_value=usage), patch.dict(os.environ, {"R4_DATA_ROOT": str(root)}):
            runner.run(args, cfg, self.limits)
            ledger_path = root/"runs"/cfg["campaign_id"]/"ledger.json"
            first = read(ledger_path)
            runner.run(args, cfg, self.limits)
            self.assertEqual(first, read(ledger_path))
        self.assertEqual(len(first["jobs"]), 2)
        self.assertTrue(all(j["outcome"]["execution_status"] == "completed" for j in first["jobs"].values()))

    def test_orphan_reservations_block_restart(self):
        self.reserve()
        self.assertEqual(self.reopen().state["jobs"]["a"]["status"], "running")
        with self.assertRaisesRegex(RuntimeError, "already attempted"):
            self.reopen().reserve("a", "E3", "GPU-other", 430, "new-sha")

    def test_frozen_cache_still_detects_same_size_edits(self):
        path = Path(self.tmp.name)/"input.json"; path.write_text("1234")
        plan = {"frozen_sha256": {str(path): digest(path)}}
        cache = {}
        with patch("r4_campaign.digest", wraps=digest) as hashed:
            assert_frozen(plan, cache); assert_frozen(plan, cache)
            self.assertEqual(hashed.call_count, 1)
            previous = path.stat()
            path.write_text("4321")
            os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            with self.assertRaisesRegex(RuntimeError, "Frozen input"):
                assert_frozen(plan, cache)


if __name__ == "__main__":
    unittest.main()
