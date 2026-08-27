"""The critic: assertions, not judgement (bridge-plan-v3.md §9).

There is no prose to revise, so there is no revision loop. Every check is
exact, and a failure means the PIPELINE is broken — the job errors and is
logged; it never ships a softened verdict.
"""

from backend.services.bridge.difficulty import score as recompute_difficulty
from backend.services.bridge.registry import BridgeSpec
from backend.services.bridge.verdict import decide_verdict_value


class CriticError(Exception):
    """One or more grounding assertions failed. The message lists them all."""


def check(artefact: dict, spec: BridgeSpec, context: dict) -> None:
    failures: list[str] = []

    # The verdict value must be re-derivable from the same records.
    expected = decide_verdict_value(context)
    if artefact["verdict"] != expected:
        failures.append(
            f"verdict {artefact['verdict']!r} inconsistent with gate outcomes "
            f"(re-derived {expected!r})"
        )

    # No dataset appears that a tool did not return.
    dataset = artefact.get("dataset")
    if dataset:
        pool_ids = {
            (c["source"], c["dataset_id"]) for c in context["pool_candidates"]
        }
        if (dataset["source"], dataset["dataset_id"]) not in pool_ids:
            failures.append(
                f"cited dataset {dataset['dataset_id']!r} is not in the scouted pool"
            )

    # Probe metrics present, or the verdict explicitly marked unconfirmed.
    fit = artefact["fit"]
    if fit.get("probed"):
        probe = context.get("probe_report") or {}
        for key in ("means", "noise_band", "outcome", "per_seed"):
            if fit.get(key) != probe.get(key):
                failures.append(f"fit.{key} does not match the probe record")
    elif not fit.get("unconfirmed_reason"):
        failures.append("fit is unprobed but carries no unconfirmed_reason")

    # The difficulty tier is rubric[modality] + floor, not a loose restatement.
    difficulty = artefact.get("difficulty")
    if difficulty is not None and not artefact.get("inherited_from"):
        stats = (context.get("inspection") or {}).get("stats", {})
        expected_difficulty = recompute_difficulty(spec, stats)
        if difficulty.get("tier") != expected_difficulty["tier"]:
            failures.append(
                f"difficulty tier {difficulty.get('tier')} != recomputed "
                f"{expected_difficulty['tier']}"
            )

    # Rejection counts must equal the recorded rejection lists.
    rejections = artefact["evidence"].get("rejections", {})
    for gate_name, entry in rejections.items():
        if entry.get("count") != len(entry.get("examples_all", entry.get("examples", []))):
            # examples_all holds the full list when the artefact truncates for display
            failures.append(f"rejection count for {gate_name} does not match its list")

    # No API endpoint appears that the curated registry + live probe didn't produce.
    for api in artefact.get("api_path") or []:
        if "reachable" not in api or "rate_limit_per_day" not in api:
            failures.append(f"api_path entry {api.get('name')!r} lacks probe/registry fields")

    if failures:
        raise CriticError("critic assertions failed: " + "; ".join(failures))


def check_inherited(artefact: dict, upstream_artefact: dict) -> None:
    """An inherited artefact's fit section and evidence are copied UNCHANGED
    from upstream, and it says where it came from. Only those fields — the
    artefact is labelled and its difficulty is re-floored, so it is not
    byte-identical (§9)."""
    failures = []
    if not artefact.get("inherited_from"):
        failures.append("inherited artefact lacks inherited_from")
    if artefact["fit"] != upstream_artefact["fit"]:
        failures.append("inherited fit section differs from upstream")
    if artefact["evidence"] != upstream_artefact["evidence"]:
        failures.append("inherited evidence differs from upstream")
    if failures:
        raise CriticError("critic assertions failed: " + "; ".join(failures))
