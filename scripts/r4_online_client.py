"""Simulation-side JSON client. Only explicitly constructed public fields pass."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time


class OnlineClient:
    def __init__(self, header, output, timeout=300):
        self.output, self.timeout = output, timeout
        self.deadline = time.monotonic()+timeout
        self.log = (output/"policy.stderr.log").open("w")
        self.history = (output/"policy-events.jsonl").open("x")
        self.audit = (output/"policy-public-input.jsonl").open("x")
        env = {k: os.environ[k] for k in ["PATH", "LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CONDA_PREFIX", "PYTORCH_KERNEL_CACHE_PATH", "CUDA_CACHE_PATH"] if k in os.environ}
        env.update(CUBLAS_WORKSPACE_CONFIG=":4096:8", PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", OMP_NUM_THREADS="8")
        self.process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).with_name("r4_online_worker.py"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1, close_fds=True, env=env)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            self.send(header)
            self.ready = self.receive()
            if not self.ready.get("ready"):
                raise RuntimeError("Policy did not initialize")
        except BaseException:
            self.close()
            raise

    def send(self, value):
        wire = json.dumps(value, allow_nan=False)
        self.audit.write(wire+"\n")
        self.audit.flush()
        self.process.stdin.write(wire+"\n")
        self.process.stdin.flush()

    def receive(self):
        remaining = self.deadline-time.monotonic()
        if remaining <= 0 or not self.selector.select(remaining):
            raise TimeoutError("GPU policy exceeded episode wall budget")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("GPU policy exited; see policy.stderr.log")
        return json.loads(line)

    def step(self, observation, reference):
        self.send({"observation": observation, "reference": reference})
        result = self.receive()
        self.history.write(json.dumps({"time_s": observation["time_s"], **result}, allow_nan=False)+"\n")
        self.history.flush()
        return result["command"]

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.selector.close()
        self.log.close()
        self.history.close()
        self.audit.close()
