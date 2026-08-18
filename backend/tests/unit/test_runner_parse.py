"""services/runner.py — the pure half: RESULT-line parsing and argv assembly.

Everything here runs without spawning a process. The subprocess half (timeouts,
aborts, heartbeats, exit codes) is covered in the integration tier against a
stub binary.
"""

import pytest

from backend.services.runner import RESULT_PREFIX, RunOutcome, _parse_result_line, build_argv
from backend.services.params import validate
from backend.services.registry import MODELS, ModelSpec, choice, integer, number


# --------------------------------------------------------------------------- #
# _parse_result_line
# --------------------------------------------------------------------------- #

def test_a_trailing_result_line_is_parsed_into_a_dict():
    stdout = 'epoch 1 loss 0.5\nepoch 2 loss 0.3\nRESULT {"final_loss": 0.3}\n'
    assert _parse_result_line(stdout) == {"final_loss": 0.3}


def test_the_last_result_line_wins():
    """Scanned backwards on purpose: only the final RESULT is authoritative."""
    stdout = 'RESULT {"n": 1}\nRESULT {"n": 2}\n'
    assert _parse_result_line(stdout) == {"n": 2}


def test_progress_lines_above_the_result_are_ignored():
    stdout = "\n".join(f"epoch {i} loss 0.1 acc 99.0%" for i in range(200))
    stdout += '\nRESULT {"final_accuracy": 0.99}'
    assert _parse_result_line(stdout) == {"final_accuracy": 0.99}


def test_stdout_with_no_result_line_yields_none():
    assert _parse_result_line("epoch 1 loss 0.5\ndone\n") is None
    assert _parse_result_line("") is None


def test_a_bare_result_word_without_a_space_does_not_match():
    """The prefix includes the trailing space, so `RESULT` alone is just text."""
    assert _parse_result_line("RESULT\n") is None
    assert _parse_result_line("RESULTS {}\n") is None


def test_a_result_line_must_start_the_line_not_merely_appear_in_it():
    assert _parse_result_line('the RESULT {"n": 1} was good\n') is None


def test_unparseable_json_yields_none_rather_than_raising():
    assert _parse_result_line("RESULT {not json}\n") is None
    assert _parse_result_line('RESULT {"a": 1} trailing garbage\n') is None


@pytest.mark.parametrize("payload", ["[1, 2]", "5", '"a string"', "null", "true"])
def test_valid_json_that_is_not_an_object_yields_none(payload):
    """The caller expects a mapping of result fields; a bare scalar or list
    would break every consumer downstream."""
    assert _parse_result_line(f"{RESULT_PREFIX}{payload}\n") is None


def test_an_empty_result_object_parses_and_is_distinct_from_none():
    """`{}` is falsy but not None, and the runner treats "parsed" as success —
    so an empty object counts as a successful run with no fields."""
    parsed = _parse_result_line("RESULT {}\n")
    assert parsed == {}
    assert parsed is not None


def test_a_diverged_run_with_null_metrics_still_parses_as_a_success():
    """Both C++ drivers emit JSON nulls when training diverges. That is a valid
    result object, so the job succeeds — and the SPA's typeof guard is what
    stops `null * 100 === 0` rendering a confident "0.0%"."""
    line = 'RESULT {"final_loss": null, "final_accuracy": null, "diverged": true}'
    assert _parse_result_line(line) == {
        "final_loss": None, "final_accuracy": None, "diverged": True,
    }


# --------------------------------------------------------------------------- #
# RunOutcome.ok — three states, not two
# --------------------------------------------------------------------------- #

def test_a_run_is_ok_only_when_it_neither_errored_nor_was_aborted():
    assert RunOutcome(stdout="", exit_code=0, result={}, error=None).ok is True
    assert RunOutcome(stdout="", exit_code=1, result=None, error="boom").ok is False
    # An aborted run carries no error — the worker requeues rather than fails it,
    # so it is neither ok nor errored.
    aborted = RunOutcome(stdout="", exit_code=None, result=None, error=None, aborted=True)
    assert aborted.ok is False
    assert aborted.error is None


# --------------------------------------------------------------------------- #
# build_argv
# --------------------------------------------------------------------------- #

def _spec() -> ModelSpec:
    return ModelSpec(
        model_id="demo",
        name="Demo",
        description="",
        binary="/opt/models/nn",
        params=(
            choice("dataset", "--dataset", ("tiny", "xor"), "tiny", label="Dataset"),
            number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate"),
            integer("epochs", "--epochs", 1, 5000, 500, label="Epochs"),
        ),
        result_fields=(),
    )


def test_argv_starts_with_the_binary_from_the_spec_and_follows_spec_order():
    spec = _spec()
    assert build_argv(spec, validate(spec, {})) == [
        "/opt/models/nn",
        "--dataset", "tiny",
        "--lr", "0.5",
        "--epochs", "500",
    ]


def test_argv_is_a_list_so_nothing_reaches_a_shell():
    """Popen is called with a list and shell=False, so no value can inject a
    second command however it is spelled."""
    spec = _spec()
    argv = build_argv(spec, validate(spec, {"dataset": "xor"}))
    assert all(isinstance(token, str) for token in argv)
    assert argv[0] == "/opt/models/nn"


def test_a_parameter_missing_from_an_older_job_row_falls_back_to_its_default():
    """Job rows are written under whatever spec was current at queue time. A
    parameter added since is simply absent, and the run should proceed on its
    default rather than fail for a reason the user had no part in."""
    spec = _spec()
    argv = build_argv(spec, {"dataset": "xor"})  # no lr, no epochs
    assert argv == ["/opt/models/nn", "--dataset", "xor", "--lr", "0.5", "--epochs", "500"]


def test_the_shipped_step0_spec_builds_the_command_line_it_documents():
    spec = MODELS["step0"]
    argv = build_argv(spec, validate(spec, {}))
    assert argv[0] == str(spec.binary)
    assert argv[1:] == [
        "--dataset", "tiny", "--lr", "0.5", "--epochs", "500", "--seed", "42",
    ]


def test_every_shipped_spec_emits_a_flag_value_pair_for_each_parameter():
    for spec in MODELS.values():
        argv = build_argv(spec, validate(spec, {}))
        assert len(argv) == 1 + 2 * len(spec.params)
        flags = argv[1::2]
        assert flags == [p.flag for p in spec.params]
        assert all(flag.startswith("--") for flag in flags)
