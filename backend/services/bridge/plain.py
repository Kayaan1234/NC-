"""Plain-language projections of the verdict record, for the dataset page.

The stored artefact is a record: slugs, tiers, outcome enums. A student should
never have to decode any of that, so this module turns each into one sentence
they read once. It is presentation, computed at serve time rather than baked
into the artefact, which means improving the wording improves every verdict
already on disk without re-running (or re-paying for) a single pipeline pass.

Nothing here names a step. The fit wording comes from the step's own ProbeSpec
(registry.plain_outcomes), so a new probe brings its own words with it.
"""

from backend.services.bridge.registry import BridgeSpec

# License slug to what it actually means for a student's project. Grouped by
# obligation, because that is the only part they need to act on.
_NO_CREDIT = "Free to use, no credit needed"
_KEEP_NOTICE = "Free to use, keep the licence notice with it"
_CREDIT = "Free to use if you credit the source"
_SHARE_ALIKE = "Free to use, but share anything you build from it the same way"

_LICENSE_PLAIN = {
    "cc0-1.0": _NO_CREDIT, "unlicense": _NO_CREDIT, "pddl": _NO_CREDIT, "wtfpl": _NO_CREDIT,
    "mit": _KEEP_NOTICE, "apache-2.0": _KEEP_NOTICE, "bsd": _KEEP_NOTICE,
    "bsd-2-clause": _KEEP_NOTICE, "bsd-3-clause": _KEEP_NOTICE, "isc": _KEEP_NOTICE,
    "cc-by-2.0": _CREDIT, "cc-by-2.5": _CREDIT, "cc-by-3.0": _CREDIT, "cc-by-4.0": _CREDIT,
    "odc-by": _CREDIT, "cdla-permissive-1.0": _CREDIT, "cdla-permissive-2.0": _CREDIT,
    "cc-by-sa-3.0": _SHARE_ALIKE, "cc-by-sa-4.0": _SHARE_ALIKE, "odbl": _SHARE_ALIKE,
    "cdla-sharing-1.0": _SHARE_ALIKE, "gpl-2.0": _SHARE_ALIKE, "gpl-3.0": _SHARE_ALIKE,
    "lgpl-3.0": _SHARE_ALIKE, "agpl-3.0": _SHARE_ALIKE,
    "openrail": "Free to use, with some restrictions on what you use it for",
}

# Difficulty tier to an expectation, not a rating. "Tier 2 of 4" tells a student
# nothing; "expect a bit of cleaning" tells them what their evening looks like.
_DIFFICULTY_PLAIN = {
    1: "Ready to use much as it comes",
    2: "Expect a bit of tidying first",
    3: "Expect real cleaning work before it trains",
    4: "A big data wrangling job on its own",
}

# When the probe could not measure anything. These live here rather than in each
# ProbeSpec because they are properties of the harness, not of any one step: any
# probe can hit a dataset with no obvious label, or run out of budget.
#
# The record's own `reason` is developer text — it has carried a raw numpy
# message ("Input X contains infinity or a value too large for dtype('float64')")
# onto a student's page before now. It stays in the evidence disclosure, and the
# sentence on the page comes from here instead. The fallback matters as much as
# the entries: an unrecognised code must still produce prose we wrote.
_UNPROBED_FALLBACK = (
    "I could not test this one myself, so have a look at the data before you commit to it."
)
_UNPROBED_WORDING = {
    "no_label": (
        "There is no obvious column to predict here, so choosing what to predict "
        "is the first thing you would decide."
    ),
    "too_slow": (
        "This one was too slow to test in the time I give it, so treat the fit as unknown."
    ),
    # Note what is NOT here: "fit_failed". It is a catch-all for anything sklearn
    # raised, and the causes have nothing in common — an all-one-class sample and
    # a column of infinities land in the same bucket. Any sentence naming a cause
    # would be wrong for the other, so it takes the fallback, which is true of
    # every case. Only add a code here when it means ONE thing.
}


def topic_title(topic: str) -> str:
    """A topic as a heading.

    Topics arrive however they were typed, and most arrive lowercase, which
    reads as sloppy at the top of a page. Only the first letter is forced: a
    student who typed "Premier League" keeps their capitals, and guessing at
    proper nouns inside the phrase would get more wrong than it fixed.
    """
    stripped = topic.strip()
    if not stripped or any(c.isupper() for c in stripped):
        return stripped
    return stripped[0].upper() + stripped[1:]


def license_line(slug: str | None) -> str:
    if not slug:
        return "Check the licence on the dataset page before you publish anything"
    return _LICENSE_PLAIN.get(slug.lower(), f"Licensed as {slug}, worth a quick read")


def difficulty_line(difficulty: dict | None) -> str | None:
    if not difficulty:
        return None
    return _DIFFICULTY_PLAIN.get(difficulty.get("tier"))


def done_line(artefact: dict, spec: BridgeSpec | None) -> str:
    """The finish line, in the second person and without jargon.

    Derived from the record rather than stored, so improving the wording
    improves every verdict already on disk. This is the one place a number
    earns its keep: a target score is how you know when to stop.

    The import is local because verdict.py imports this module; the constants
    are domain vocabulary that lives with the assembler.
    """
    from backend.services.bridge.verdict import (
        BUILDABLE_AFTER_COLLECTION,
        BUILDABLE_NOW,
        NOT_AT_THIS_STEP,
    )

    value = artefact.get("verdict")
    step = (spec.display_name if spec else artefact.get("display_name", "model")).lower()
    fit = artefact.get("fit") or {}

    if value == BUILDABLE_NOW:
        means = fit.get("means") or {}
        if fit.get("outcome") == "pass" and means:
            best = max(means.values())
            # A near-perfect target read as "around 100%" looks like a bug
            # rather than a fact about the data, even when it is one: some
            # classic sets really are separable almost every time.
            target = (
                "gets essentially every one of them right"
                if best >= 0.99
                else f"scores somewhere around {best:.0%}"
            )
            return f"You have got it working when your own {step}, trained on this data, {target}."
        return (
            f"You have got it working when your own {step} trains on this data from "
            "start to finish and you can say what score it reached."
        )
    if value == NOT_AT_THIS_STEP:
        return (
            "Pick the step this data actually suits, or pick a topic whose data needs "
            "this one. Either way you learn something real."
        )
    if value == BUILDABLE_AFTER_COLLECTION:
        api = (artefact.get("api_path") or [{}])[0]
        return (
            f"You have got it working when you have pulled about "
            f"{api.get('records_needed', 'enough')} records from "
            f"{api.get('name', 'the API')} and your own {step} trains on them."
        )
    return (
        "Try one of the nearby topics below, or pick a subject with more open data "
        "behind it. Knowing early that the data is not there is worth a lot."
    )


def fit_line(artefact: dict, spec: BridgeSpec | None) -> str | None:
    """One sentence on whether this data suits this step.

    The single most valuable line on the page: it is the thing a dataset search
    engine cannot tell you, and the only reason the pipeline fits models at all.
    """
    fit = artefact.get("fit") or {}
    if spec is not None and spec.probe is not None:
        # Prefer the finer code when the probe reported one: a FAIL that means
        # "nothing is learnable" and a FAIL that means "you need a bigger model"
        # must not read the same. Older verdicts carry no code and fall back to
        # the outcome, which is why both are looked up.
        wording = spec.probe.plain_outcomes.get(fit.get("code")) or \
            spec.probe.plain_outcomes.get(fit.get("outcome"))
        if wording:
            return wording
    if not fit.get("probed"):
        if spec is not None and spec.probe is None:
            # A step with no probe carries its own stated reason in the registry
            # (BridgeSpec.no_probe_reason), already written for students, and §4
            # requires that it be printed rather than glossed. That is curated
            # prose, not a record, so it passes straight through.
            return fit.get("unconfirmed_reason")
        return _UNPROBED_WORDING.get(fit.get("code"), _UNPROBED_FALLBACK)
    return fit.get("reason")
