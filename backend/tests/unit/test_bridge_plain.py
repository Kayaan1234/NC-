"""The serve-time wording layer (services/bridge/plain.py).

These matter more than their size suggests: plain.py is the last thing between a
stored record and a student's eyes, and it has already let a raw numpy message
("Input X contains infinity or a value too large for dtype('float64')") through
onto a dataset page. The rule these tests pin is that the sentence a student
reads is always prose we wrote, for every shape of record including ones that
predate the field being read.
"""

from backend.services.bridge import plain
from backend.services.bridge.registry import BRIDGE_SPECS


def _artefact(fit: dict) -> dict:
    return {"fit": fit}


class TestFitLine:
    def test_probe_outcome_becomes_the_step_s_own_wording(self):
        spec = BRIDGE_SPECS["step0"]
        line = plain.fit_line(_artefact({"probed": True, "outcome": "pass"}), spec)
        assert line == spec.probe.plain_outcomes["pass"]

    def test_a_code_outranks_the_bare_outcome(self):
        """step0 FAIL means two different things and must not read the same:
        nothing here is learnable, versus this needs a hidden layer."""
        spec = BRIDGE_SPECS["step0"]
        no_signal = plain.fit_line(
            _artefact({"probed": True, "outcome": "fail", "code": "no_signal"}), spec
        )
        needs_more = plain.fit_line(
            _artefact({"probed": True, "outcome": "fail", "code": "needs_hidden_layer"}), spec
        )
        assert no_signal != needs_more
        assert no_signal == spec.probe.plain_outcomes["no_signal"]

    def test_a_failed_fit_never_shows_the_raw_error(self):
        raw = "Input X contains infinity or a value too large for dtype('float64')."
        line = plain.fit_line(
            _artefact({"probed": False, "code": "fit_failed", "unconfirmed_reason": raw}),
            BRIDGE_SPECS["step1"],
        )
        assert raw not in line
        assert line == plain._UNPROBED_FALLBACK

    def test_a_failed_fit_does_not_blame_a_cause_it_cannot_know(self):
        """`fit_failed` covers everything sklearn can raise, and the causes are
        unrelated: this one is a sample with only one class present, not dirty
        data. Wording that named cleaning would send this student to scrub data
        that is already clean."""
        line = plain.fit_line(
            _artefact({
                "probed": False,
                "code": "fit_failed",
                "unconfirmed_reason": (
                    "variant fit failed on this data: This solver needs samples of at "
                    "least 2 classes in the data, but the data contains only one class"
                ),
            }),
            BRIDGE_SPECS["step0"],
        )
        assert "tidying" not in line and "clean" not in line

    def test_a_probed_fit_is_never_mistaken_for_an_unprobed_one(self):
        """`fit.get("probed")` is falsy for a missing key as well as False. Every
        writer sets it today; pinning it means a future one that forgets cannot
        quietly tell a student the probe did not run when it did."""
        spec = BRIDGE_SPECS["step0"]
        line = plain.fit_line(_artefact({"probed": True, "outcome": "pass"}), spec)
        assert line == spec.probe.plain_outcomes["pass"]
        assert line != plain._UNPROBED_FALLBACK

    def test_an_unknown_code_still_gets_prose_we_wrote(self):
        """Verdicts stored before the code existed carry none. The fallback is
        the point of this test: no code must ever mean no sentence, or the raw
        reason leaking back in."""
        raw = "variant fit failed on this data: something new and unhandled"
        line = plain.fit_line(
            _artefact({"probed": False, "unconfirmed_reason": raw}), BRIDGE_SPECS["step1"]
        )
        assert line == plain._UNPROBED_FALLBACK
        assert raw not in line

    def test_a_step_with_no_probe_keeps_its_curated_reason(self):
        """The opposite failure. BridgeSpec.no_probe_reason is hand-written for
        students and §4 requires it be printed, so it must NOT be swapped for
        the generic fallback just because nothing was measured."""
        spec = next(s for s in BRIDGE_SPECS.values() if s.probe is None)
        line = plain.fit_line(
            _artefact({"probed": False, "unconfirmed_reason": spec.no_probe_reason}), spec
        )
        assert line == spec.no_probe_reason


class TestTopicTitle:
    def test_lowercase_topics_get_a_capital(self):
        assert plain.topic_title("premier league results") == "Premier league results"

    def test_existing_capitals_are_left_alone(self):
        assert plain.topic_title("Premier League") == "Premier League"


class TestLicenseLine:
    def test_a_slug_becomes_an_obligation(self):
        assert "credit" in plain.license_line("cc-by-4.0").lower()

    def test_an_unknown_slug_names_itself_rather_than_guessing(self):
        """It must not silently map to a permissive-sounding phrase. Naming the
        slug and sending them to read it is the honest move."""
        line = plain.license_line("some-bespoke-license")
        assert "some-bespoke-license" in line
        assert "free to use" not in line.lower()
