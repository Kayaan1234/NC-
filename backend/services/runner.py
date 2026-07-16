"""Executes one training run as a subprocess and parses its result.

This is the only place in the codebase that spawns a process, and every choice
here is about surviving a run that lasts minutes rather than milliseconds:

  - Popen + a poll loop, not subprocess.run(). A long run has to report liveness
    while it executes; subprocess.run() blocks until exit, which would leave the
    worker unable to heartbeat and the job indistinguishable from a dead one.
  - stdout redirected to a temp file, not PIPE. With PIPE and no concurrent
    reader, a child blocks forever once it fills the OS pipe buffer (~64KB).
    Step0 can't hit that (it prints ~10 progress lines regardless of --epochs),
    but a model that streams per-epoch output would, and the poll loop above is
    exactly the "no concurrent reader" shape that deadlocks. The temp file also
    survives a kill — a timed-out run still yields its partial output for the
    report — and gives live progress somewhere to tail from later.
  - argv as a list, never a shell string. User-supplied numbers reach the process
    as distinct argv entries, so there is no quoting or injection surface.

The caller (worker.py) owns the database; this module owns the process and never
imports a model.
"""

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.core.config import settings
from backend.services.registry import ModelSpec

# The binary's own contract (see services/Step0/main.cpp): the run ends with a
# single machine-readable line, and 2 means the arguments were rejected.
RESULT_PREFIX = "RESULT "
EXIT_BAD_INPUT = 2


@dataclass
class RunOutcome:
    """What happened in one run. `error` is None iff the run is usable."""

    stdout: str
    exit_code: int | None       # None if the process was killed (timeout/abort)
    result: dict[str, Any] | None
    error: str | None
    # True if the caller asked us to stop (worker shutting down) rather than the
    # run failing on its own. The caller requeues these instead of failing them.
    aborted: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and not self.aborted


def _parse_result_line(stdout: str) -> dict[str, Any] | None:
    """Pull the trailing `RESULT {...}` JSON line out of the run's stdout.

    Scans backwards: the progress lines above it are free text, and only the last
    RESULT line is authoritative. Returns None if it's absent or unparseable —
    the caller decides whether that's fatal.
    """
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            try:
                parsed = json.loads(line[len(RESULT_PREFIX):])
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def build_argv(spec: ModelSpec, params: dict[str, Any]) -> list[str]:
    """Assemble the command line for one run.

    `params` must already be validated (schema bounds + spec.datasets) — this
    function assumes its caller did that and only handles formatting. The binary
    path comes from the spec, never from anything a request supplied.
    """
    return [
        str(spec.binary),
        "--dataset", str(params["dataset"]),
        "--lr", repr(float(params["lr"])),
        "--epochs", str(int(params["epochs"])),
        "--seed", str(int(params["seed"])),
    ]


def run_training(
    spec: ModelSpec,
    params: dict[str, Any],
    on_heartbeat: Callable[[], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> RunOutcome:
    """Run one training job to completion, a timeout, an abort, or a failure.

    `on_heartbeat` is invoked every JOB_HEARTBEAT_SECONDS while the process is
    alive. The worker uses it to prove the job is still being supervised; a
    healthy long run and a dead worker are otherwise identical from the outside.

    `should_abort` is polled each tick; returning True kills the process
    promptly. Without it, a worker asked to shut down would have to wait out the
    job — fine for Step0's milliseconds, but a deploy would hang for the length
    of a real training run. This is also the seam a user-facing cancel button
    plugs into.

    Never raises for an expected failure — a bad exit, a timeout, or a missing
    binary all come back as a RunOutcome with `error` set, because every one of
    them must land in the job row rather than crash the worker loop.
    """
    argv = build_argv(spec, params)

    # delete=False: we reopen by name after the child exits. Closed and unlinked
    # in the finally below, on every path.
    tmp = tempfile.NamedTemporaryFile(
        mode="w+", suffix=".log", prefix=f"train-{spec.model_id}-", delete=False
    )
    try:
        try:
            proc = subprocess.Popen(
                argv,
                stdout=tmp,
                stderr=subprocess.STDOUT,  # diagnostics belong in the report too
                cwd=spec.binary.parent,
                text=True,
            )
        except FileNotFoundError:
            return RunOutcome(
                stdout="",
                exit_code=None,
                result=None,
                error=(
                    f"Model binary not built: {spec.binary}. "
                    f"Run `make` in {spec.binary.parent}."
                ),
            )
        except OSError as exc:
            return RunOutcome("", None, None, f"Could not start training process: {exc}")

        timed_out = False
        aborted = False
        deadline = time.monotonic() + spec.timeout_seconds
        # Beat once immediately: monotonic() is always far above 0, so the first
        # comparison fires on entry. The claim already stamped a heartbeat, and
        # starting the cadence here keeps a slow first tick from looking stale.
        last_beat = 0.0
        while proc.poll() is None:
            # kill(), not terminate(): a compute-bound binary with no signal
            # handling and nothing to flush has no graceful path worth waiting on.
            if should_abort is not None and should_abort():
                proc.kill()
                proc.wait()
                aborted = True
                break
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                timed_out = True
                break
            now = time.monotonic()
            if on_heartbeat is not None and now - last_beat >= settings.JOB_HEARTBEAT_SECONDS:
                on_heartbeat()
                last_beat = now
            time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)

        tmp.flush()
        with open(tmp.name, encoding="utf-8", errors="replace") as fh:
            stdout = fh.read()
    finally:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if aborted:
        # Not an error: the run was interrupted by us, and the caller will requeue
        # it. Deliberately leaves `error` unset so nothing user-facing blames the
        # user's parameters for our shutdown.
        return RunOutcome(stdout=stdout, exit_code=None, result=None, error=None, aborted=True)

    if timed_out:
        return RunOutcome(
            stdout=stdout,
            exit_code=None,
            result=None,
            error=f"Training exceeded its {spec.timeout_seconds}s time limit and was stopped.",
        )

    exit_code = proc.returncode
    result = _parse_result_line(stdout)

    if exit_code == EXIT_BAD_INPUT:
        return RunOutcome(stdout, exit_code, result, "Training rejected the supplied parameters.")
    if exit_code != 0:
        return RunOutcome(stdout, exit_code, result, f"Training exited with code {exit_code}.")
    if result is None:
        # Clean exit with no parseable RESULT line means the contract broke —
        # treat it as a failure rather than reporting a success with no numbers.
        return RunOutcome(stdout, exit_code, None, "Training produced no readable RESULT line.")

    return RunOutcome(stdout, exit_code, result, None)
