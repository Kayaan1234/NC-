"""services/runner.py — the subprocess half: all seven RunOutcome shapes.

No compiled binary is needed. `build_argv` sets argv[0] = str(spec.binary) and
Popen is called with a list, so a chmod+x shell script AT that path is the
executable — nothing can precede it, which is why these are shebang scripts
rather than `["python", script]`.

The real Step0/Step1 `nn` binaries are gitignored and absent in CI, so the one
test that uses a real binary is gated on its existence.
"""

import os
import stat
from pathlib import Path

import pytest

from backend.core.config import settings
from backend.services import runner
from backend.services.registry import MODELS, ModelSpec, choice
from backend.services.runner import run_training


@pytest.fixture()
def stub_binary(tmp_path):
    """Write an executable script and return a ModelSpec pointing at it.

    The script must tolerate arbitrary `--flag value` arguments, since build_argv
    emits one pair per spec parameter.
    """
    def _make(script: str, *, timeout_seconds: int = 5) -> ModelSpec:
        path = tmp_path / "nn"
        path.write_text(script)
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return ModelSpec(
            model_id="stub",
            name="Stub",
            description="",
            binary=path,
            params=(choice("dataset", "--dataset", ("tiny",), "tiny", label="Dataset"),),
            result_fields=(),
            timeout_seconds=timeout_seconds,
        )

    return _make


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch):
    """The runner reads both of these at call time, so the loop can be sped up
    without touching wall-clock waits anywhere else."""
    monkeypatch.setattr(settings, "JOB_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "JOB_HEARTBEAT_SECONDS", 0.01)


# --------------------------------------------------------------------------- #
# 1 & 2: the process never starts
# --------------------------------------------------------------------------- #

def test_a_missing_binary_reports_how_to_build_it(tmp_path):
    spec = ModelSpec(
        model_id="stub", name="Stub", description="",
        binary=tmp_path / "does-not-exist",
        params=(choice("dataset", "--dataset", ("tiny",), "tiny", label="Dataset"),),
        result_fields=(),
    )
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code is None
    assert outcome.result is None
    assert "Model binary not built" in outcome.error
    assert "make" in outcome.error


def test_a_binary_that_is_not_executable_reports_a_start_failure(stub_binary):
    spec = stub_binary("#!/bin/sh\nexit 0\n")
    Path(spec.binary).chmod(0o644)  # readable, not executable

    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code is None
    assert "Could not start training process" in outcome.error


# --------------------------------------------------------------------------- #
# 3 & 4: success and a missing RESULT line
# --------------------------------------------------------------------------- #

def test_a_clean_run_with_a_result_line_succeeds(stub_binary):
    spec = stub_binary(
        '#!/bin/sh\n'
        'echo "epoch 1 loss 0.5"\n'
        'echo \'RESULT {"final_loss": 0.25, "final_accuracy": 0.99}\'\n'
        'exit 0\n'
    )
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is True
    assert outcome.exit_code == 0
    assert outcome.error is None
    assert outcome.result == {"final_loss": 0.25, "final_accuracy": 0.99}
    assert "epoch 1 loss 0.5" in outcome.stdout


def test_a_clean_exit_with_no_result_line_is_a_failure(stub_binary):
    """Exit 0 is not enough — without a RESULT line there is nothing to show the
    user, so the job fails rather than succeeding emptily."""
    spec = stub_binary('#!/bin/sh\necho "training..."\nexit 0\n')
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code == 0
    assert outcome.result is None
    assert "no readable RESULT line" in outcome.error


def test_stderr_is_folded_into_the_captured_output(stub_binary):
    """Diagnostics belong in the report too — that is what the report is for."""
    spec = stub_binary(
        '#!/bin/sh\necho "to stderr" >&2\necho \'RESULT {"a": 1}\'\nexit 0\n'
    )
    outcome = run_training(spec, {"dataset": "tiny"})
    assert "to stderr" in outcome.stdout


# --------------------------------------------------------------------------- #
# 5 & 6: non-zero exits
# --------------------------------------------------------------------------- #

def test_exit_code_two_is_reported_as_rejected_parameters(stub_binary):
    """The binary's own contract: 2 means it refused the arguments."""
    spec = stub_binary('#!/bin/sh\necho "bad --lr" >&2\nexit 2\n')
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code == 2
    assert outcome.error == "Training rejected the supplied parameters."


def test_any_other_non_zero_exit_reports_its_code(stub_binary):
    spec = stub_binary('#!/bin/sh\nexit 3\n')
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code == 3
    assert outcome.error == "Training exited with code 3."


def test_a_result_line_is_still_parsed_from_a_failed_run(stub_binary):
    """Partial output is more use than none when working out what went wrong."""
    spec = stub_binary('#!/bin/sh\necho \'RESULT {"partial": true}\'\nexit 3\n')
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.result == {"partial": True}


# --------------------------------------------------------------------------- #
# 7 & 8: timeout and abort
# --------------------------------------------------------------------------- #

def test_a_run_that_overruns_its_timeout_is_killed_and_reported(stub_binary):
    spec = stub_binary('#!/bin/sh\nsleep 30\n', timeout_seconds=1)
    outcome = run_training(spec, {"dataset": "tiny"})

    assert outcome.ok is False
    assert outcome.exit_code is None  # killed, so there is no clean exit status
    assert "exceeded its 1s time limit" in outcome.error


def test_a_timed_out_run_still_returns_the_output_it_produced(stub_binary):
    """stdout goes to a temp file rather than a pipe precisely so a killed run
    still yields whatever it managed to print."""
    spec = stub_binary('#!/bin/sh\necho "got this far"\nsleep 30\n', timeout_seconds=1)
    outcome = run_training(spec, {"dataset": "tiny"})
    assert "got this far" in outcome.stdout


def test_an_aborted_run_is_neither_ok_nor_errored(stub_binary):
    """Shutdown is not a failure: the worker requeues these rather than failing
    them, so `aborted` is set and `error` stays None."""
    spec = stub_binary('#!/bin/sh\nsleep 30\n', timeout_seconds=60)

    outcome = run_training(spec, {"dataset": "tiny"}, should_abort=lambda: True)

    assert outcome.aborted is True
    assert outcome.error is None
    assert outcome.ok is False
    assert outcome.exit_code is None


def test_abort_is_checked_before_the_deadline(stub_binary):
    """Both would fire; the abort wins, so a worker shutting down during an
    overrunning job requeues it instead of recording a timeout failure."""
    spec = stub_binary('#!/bin/sh\nsleep 30\n', timeout_seconds=0)

    outcome = run_training(spec, {"dataset": "tiny"}, should_abort=lambda: True)

    assert outcome.aborted is True
    assert outcome.error is None


# --------------------------------------------------------------------------- #
# Heartbeats
# --------------------------------------------------------------------------- #

def test_a_long_run_emits_heartbeats(stub_binary):
    """The heartbeat is what keeps a legitimately slow job out of the stale
    reclaim — without it, a 20-minute run would be failed as a dead worker."""
    beats = []
    spec = stub_binary('#!/bin/sh\nsleep 0.4\necho \'RESULT {}\'\n', timeout_seconds=30)

    run_training(spec, {"dataset": "tiny"}, on_heartbeat=lambda: beats.append(1))

    assert beats, "a run longer than the heartbeat interval must beat at least once"


def test_a_run_needs_no_heartbeat_callback(stub_binary):
    spec = stub_binary('#!/bin/sh\necho \'RESULT {}\'\n')
    assert run_training(spec, {"dataset": "tiny"}).ok is True


# --------------------------------------------------------------------------- #
# Housekeeping and argv
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "script,timeout",
    [
        ('#!/bin/sh\necho \'RESULT {}\'\n', 5),   # success
        ('#!/bin/sh\nexit 3\n', 5),               # non-zero exit
        ('#!/bin/sh\nsleep 30\n', 1),             # killed on timeout
    ],
    ids=["success", "failure", "timeout"],
)
def test_the_temporary_log_file_is_removed_on_every_path(stub_binary, monkeypatch, script, timeout):
    """The unlink is in a `finally`, so it has to survive a kill as well as a
    clean exit. Captures the real path rather than globbing the temp directory —
    a glob-and-compare passes even with the unlink deleted, since both sides are
    empty.
    """
    created: list[str] = []
    real = runner.tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        handle = real(*args, **kwargs)
        created.append(handle.name)
        return handle

    monkeypatch.setattr(runner.tempfile, "NamedTemporaryFile", spy)

    run_training(stub_binary(script, timeout_seconds=timeout), {"dataset": "tiny"})

    assert created, "the runner did not create a log file at all"
    assert not Path(created[0]).exists(), f"{created[0]} was left behind"


def test_the_process_receives_the_flags_the_spec_declares(stub_binary):
    spec = stub_binary('#!/bin/sh\necho "argv: $@"\necho \'RESULT {}\'\n')
    outcome = run_training(spec, {"dataset": "tiny"})
    assert "argv: --dataset tiny" in outcome.stdout


def test_a_parameter_value_cannot_inject_a_second_command(stub_binary, tmp_path):
    """Popen gets a list with shell=False, so this is structural rather than a
    matter of escaping — but assert it, because the day someone "simplifies" it
    to a string is the day it matters."""
    marker = tmp_path / "pwned"  # test-scoped, so a stale file can't fake a pass
    spec = stub_binary('#!/bin/sh\necho "argv: $@"\necho \'RESULT {}\'\n')

    outcome = run_training(spec, {"dataset": f"tiny; touch {marker}"})

    assert f"; touch {marker}" in outcome.stdout  # passed through as ONE argument
    assert not marker.exists()


def test_the_process_runs_from_the_binarys_own_directory(stub_binary):
    """Load-bearing for Step1: its registry entry has no --data-dir parameter, so
    the binary falls back to a relative "data" path. Run it from anywhere else
    and MNIST fails to load."""
    spec = stub_binary('#!/bin/sh\necho "cwd: $(pwd)"\necho \'RESULT {}\'\n')
    outcome = run_training(spec, {"dataset": "tiny"})
    assert str(Path(spec.binary).parent) in outcome.stdout


# --------------------------------------------------------------------------- #
# The one real-binary check
# --------------------------------------------------------------------------- #

@pytest.mark.requires_binary
@pytest.mark.skipif(
    not Path(MODELS["step0"].binary).exists(),
    reason="Step0 nn is gitignored and not built here; run `make` in services/Step0",
)
def test_the_real_step0_binary_trains_the_tiny_dataset():
    """Cross-checks the whole contract — argv, exit code, RESULT line — against
    the actual C++ driver. Sub-second on the tiny dataset."""
    from backend.services.params import validate

    spec = MODELS["step0"]
    outcome = run_training(spec, validate(spec, {"dataset": "tiny", "epochs": 50}))

    assert outcome.ok is True, outcome.error
    assert outcome.exit_code == 0
    assert "final_accuracy" in outcome.result
