"""The verdict artefact assembler (bridge-plan-v3.md §8) — and LLM call site 3
of 3, the one generated sentence.

Almost every field is copied from records the tools, gates and probe produced;
the LLM writes exactly one sentence on top. Maximally specific about what is
true, minimally prescriptive about what to do: no code, no layer sizes, no
ordered preprocessing steps.

One deliberate extension to §8's three verdict values: `not_at_this_step`, for
the §19 failure mode where a real dataset exists but the probe shows it does
not demonstrate what THIS step needs (e.g. the hidden layer buys nothing at
step1). Folding that into "not at hobby scale" would be false, and into
"buildable now" falser; the fourth value is what §19's "refusing to invent a
bad project is a feature" looks like as data.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.bridge import plain
from backend.services.bridge.gates import SCALE_READINGS
from backend.services.bridge.llm import SpendLedger, call_structured
from backend.services.bridge.registry import BridgeSpec, ProbeOutcome

logger = logging.getLogger("backend.bridge.verdict")

BUILDABLE_NOW = "buildable_now"
BUILDABLE_AFTER_COLLECTION = "buildable_after_collection"
NOT_AT_THIS_STEP = "not_at_this_step"
NOT_AT_HOBBY_SCALE = "not_at_hobby_scale"


class SummarySentence(BaseModel):
    sentence: str  # one sentence; the output budget is the real cap


_SUMMARY_STATIC = """You are a student telling a friend what you found, in ONE short sentence.

Your friend is learning to build neural networks from scratch in C++ and wants a real dataset
to practise on. Say what the data actually contains and why it does or does not suit the
project they picked.

Rules:
  - One sentence, under 25 words, warm and plain, the way you would say it out loud.
  - No jargon at all. Never write "noise band", "validation gap", "probe", "modality",
    "metric", "baseline", "multilayer perceptron", and never quote an accuracy figure.
  - Never use an em-dash or a semicolon. Short words and commas only.
  - Do not restate the verdict label, the reader can already see it above your sentence.
  - Use only the facts given. Never invent a number, a name or a source.

Return JSON with the single field `sentence`."""


# What the probe outcome MEANS, in words, per step. Passed to the summary call
# instead of the probe's own expert-facing reason string, which is written for
# someone reading metrics and leaks jargon straight into the sentence.
_PLAIN_FIT = {
    ProbeOutcome.PASS.value: "this data suits the chosen model well",
    ProbeOutcome.FAIL.value: "this data does not show what the chosen model is for",
    ProbeOutcome.UNCONFIRMED.value: "this data works about as well with a simpler model",
}


def decide_verdict_value(context: dict) -> str:
    """The deterministic mapping from what happened to what the verdict says —
    the critic re-derives this same mapping, so drift is a hard failure."""
    if context.get("dataset"):
        probe = context.get("probe_report") or {}
        if probe.get("outcome") == ProbeOutcome.FAIL.value:
            return NOT_AT_THIS_STEP
        return BUILDABLE_NOW
    if any(a.get("reachable") for a in context.get("api_assessments") or []):
        return BUILDABLE_AFTER_COLLECTION
    return NOT_AT_HOBBY_SCALE


def _fit_section(spec: BridgeSpec, context: dict) -> dict:
    probe = context.get("probe_report")
    if probe and "means" in probe:
        return {
            "probed": True,
            "outcome": probe["outcome"],
            "code": probe.get("code", probe["outcome"]),
            "reason": probe["reason"],
            "metric": probe["metric"],
            "means": probe["means"],
            "noise_band": probe["noise_band"],
            "per_seed": probe["per_seed"],
            "rows_used": probe["rows_used"],
        }
    if probe:  # probe ran but couldn't measure (no label, over budget, fit error)
        # The code travels with the reason: the reason is the record (and the
        # evidence disclosure shows it), the code is what plain.py turns into
        # the sentence on the page.
        return {"probed": False, "code": probe.get("code"),
                "unconfirmed_reason": probe["reason"],
                "corpus_stats": (context.get("inspection") or {}).get("stats", {})}
    return {
        "probed": False,
        "unconfirmed_reason": spec.no_probe_reason,
        "corpus_stats": (context.get("inspection") or {}).get("stats", {}),
    }


def assemble(
    db: Session,
    ledger: SpendLedger,
    spec: BridgeSpec,
    topic_display: str,
    context: dict,
) -> dict:
    """Build the artefact from records, then ask for its one sentence."""
    value = decide_verdict_value(context)
    dataset = context.get("dataset")
    fit = _fit_section(spec, context)
    reading = SCALE_READINGS[spec.modality]

    artefact: dict = {
        "verdict": value,
        "topic": topic_display,
        "model_id": spec.model_id,
        "display_name": spec.display_name,
        "capability": spec.capability,
        "modality": spec.modality.value,
        "evidence": context["evidence"],
        "dataset": dataset and {
            **dataset,
            "scale_unit": reading.unit,
            "scale": (context.get("inspection") or {}).get("stats", {}),
        },
        "fit": fit,
        "difficulty": context.get("difficulty"),
        "api_path": context.get("api_assessments") or None,
        "nearest_domain": context.get("nearest_domain") or None,
        "inherited_from": None,
        "assumptions": _assumptions(spec, context),
    }
    # Derived from the finished artefact by the same function that serves it,
    # so a stored verdict and a freshly rendered one can never disagree.
    artefact["definition_of_done"] = plain.done_line(artefact, spec)

    write_summary(db, ledger, artefact)
    return artefact


def summary_facts(artefact: dict) -> dict:
    """What the summary call is allowed to see.

    Deliberately NOT the probe's own reason string or any figure: those are
    written for someone reading metrics, and whatever goes in here comes back
    out in the sentence a student reads. Built from the finished artefact so
    the pipeline and the CLI's re-summarise cannot drift apart.
    """
    dataset = artefact.get("dataset")
    scale = (dataset or {}).get("scale") or {}
    return {
        "topic": artefact["topic"],
        "project": artefact["display_name"],
        "what_the_data_must_show": artefact["capability"],
        "dataset_found": bool(dataset),
        "dataset_name": dataset and dataset.get("title"),
        "rows": scale.get("num_rows"),
        "columns": scale.get("num_columns"),
        "how_well_it_fits": _PLAIN_FIT.get(
            (artefact.get("fit") or {}).get("outcome"), "the fit could not be measured"
        ),
        "collect_it_yourself_from": [a["name"] for a in artefact.get("api_path") or []],
    }


def write_summary(db: Session, ledger: SpendLedger, artefact: dict) -> str:
    """Generate and attach the artefact's one sentence. The only prose the
    pipeline generates, and the only place it is generated."""
    summary = call_structured(
        db, ledger, "verdict_summary",
        static_instructions=_SUMMARY_STATIC,
        user_text=str(summary_facts(artefact)),
        response_model=SummarySentence,
    )
    artefact["summary"] = summary.sentence
    return summary.sentence


def _assumptions(spec: BridgeSpec, context: dict) -> list[str]:
    """Every approximation the verdict rests on, printed (§6: transparently
    approximate beats confidently vague)."""
    reading = SCALE_READINGS[spec.modality]
    assumptions = [
        f"scale floor for {spec.modality.value}: {reading.floor} examples",
    ]
    probe = context.get("probe_report")
    if probe and "means" in probe:
        assumptions.append(
            f"probe: {probe['rows_used']} rows (cap {probe['row_cap']}), "
            f"seeds {probe['seeds']}, metric {probe['metric']}, held-out 25%"
        )
    for api in context.get("api_assessments") or []:
        assumptions.append(
            f"{api['name']} collection estimate assumes 1 record/request at "
            f"{api['rate_limit_per_day']} requests/day (documented free tier)"
        )
    return assumptions


def build_inherited(upstream_artefact: dict, spec: BridgeSpec, upstream_id: str) -> dict:
    """An INHERITS_VERDICT step's artefact: fit and evidence copied UNCHANGED
    from upstream (§9's assertion covers exactly those fields), difficulty
    re-floored for the inheriting step, summary derived not regenerated."""
    artefact = {
        **upstream_artefact,
        "model_id": spec.model_id,
        "display_name": spec.display_name,
        "capability": spec.capability,
        "inherited_from": upstream_id,
        "summary": f"(inherited from {upstream_id}) {upstream_artefact['summary']}",
        "definition_of_done": (
            f"Done when your {spec.display_name} reproduces {upstream_id}'s result on the "
            "same data with zero hand-written gradients."
        ),
    }
    upstream_difficulty = upstream_artefact.get("difficulty")
    if upstream_difficulty:
        artefact["difficulty"] = {
            **upstream_difficulty,
            "step_floor": spec.difficulty_floor,
            "tier": max(upstream_difficulty["rubric_tier"], spec.difficulty_floor),
        }
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    artefact["assumptions"] = [
        *upstream_artefact.get("assumptions", []),
        f"inherited from {upstream_id} at {now}: the checkpoint re-implements its model, "
        "so the data question is identical",
    ]
    return artefact
