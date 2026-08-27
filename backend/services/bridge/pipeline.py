"""The pipeline: one bridge job in, one stored verdict out.

Orchestrates the stages of bridge-plan-v3.md's architecture diagram — plan →
scout fan-out → gates → replan (≤2) → probe → difficulty → assemble → critic —
branching only on descriptor fields (data_requirement, probe is None), never on
step identity. Runs on the worker, inside the bridge drain thread.

Failure discipline:
  - BudgetExceeded / PipelineTimeout  → the job fails with an honest message
    (partial evidence, ceiling reached) — never a stack trace.
  - CriticError                       → the job fails loudly as a pipeline bug;
    a softened verdict is never shipped (§9).
  - Anything else                     → the drain loop's catch-all records it.

Idempotency: a re-claimed job (worker died mid-run) first checks whether the
verdict already exists, and every paid call it replays hits bridge_llm_cache —
that is the whole mitigation for the queue's at-least-once delivery.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.Bridge import (
    BridgeJob,
    BridgeJobSource,
    BridgeVerdict,
    BridgeVerdictStatus,
)
from backend.services.bridge import card_index, critic, tools, verdict as verdict_mod
from backend.services.bridge.api_path import assess_api_path
from backend.services.bridge.difficulty import score as score_difficulty
from backend.services.bridge.gates import gate1_license, gate2_loadable, gate3_scale
from backend.services.bridge.judge import judge_relevance
from backend.services.bridge.llm import BudgetExceeded, SpendLedger
from backend.services.bridge.planner import MAX_REPLANS, plan_queries
from backend.services.bridge.recents import record_search_quietly
from backend.services.bridge.registry import (
    BridgeSpec,
    DataRequirement,
    ProbeOutcome,
    get_spec,
)
from backend.services.bridge.scouts import active_scouts
from backend.services.bridge.tracing import ProgressLog, span

logger = logging.getLogger("backend.bridge.pipeline")

MAX_FINALISTS = 3


class PipelineTimeout(Exception):
    pass


class _Deadline:
    def __init__(self, seconds: int) -> None:
        self._until = time.monotonic() + seconds

    def check(self, stage: str) -> None:
        if time.monotonic() > self._until:
            raise PipelineTimeout(f"run exceeded {settings.BRIDGE_RUN_TIMEOUT_SECONDS}s during {stage}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _rollback_quietly(db: Session) -> None:
    """Clear a pending-rollback state so the failure can be recorded on the job
    row. On a healthy session this is a no-op; only a dropped connection makes
    it raise, and that case belongs to the drain loop's reset_session."""
    db.rollback()


def _get_verdict_row(db: Session, topic_slug: str, model_id: str) -> BridgeVerdict | None:
    return db.execute(
        select(BridgeVerdict).where(
            BridgeVerdict.topic_slug == topic_slug,
            BridgeVerdict.model_id == model_id,
        )
    ).scalars().first()


def _store_verdict(db: Session, job: BridgeJob, model_id: str, artefact: dict) -> BridgeVerdict:
    row = _get_verdict_row(db, job.topic_slug, model_id)
    if row is None:
        row = BridgeVerdict(
            topic_slug=job.topic_slug,
            model_id=model_id,
            topic_display=job.topic_input,
            verdict=artefact,
            status=BridgeVerdictStatus.DRAFT.value,
            inherited_from=artefact.get("inherited_from"),
            produced_by_job=job.id,
        )
        db.add(row)
    else:
        row.verdict = artefact
        row.inherited_from = artefact.get("inherited_from")
        row.produced_by_job = job.id
        row.last_verified = _utcnow()
    db.commit()
    return row


def _remember_search(db: Session, job: BridgeJob) -> None:
    """Put a finished job's topic in its requester's recent-searches list.

    Only for a job that has both a student behind it and a verdict to open. Seed
    jobs carry no user_id and must never occupy a slot in anyone's list.

    Records job.model_id alone. An INHERITS_VERDICT run builds its upstream
    step's verdict on the way past, but the student asked about *this* step, and
    listing a step they never searched under "your recent searches" would be a
    small lie the page has no way to explain.
    """
    if job.user_id is None or job.source != BridgeJobSource.LIVE.value:
        return
    record_search_quietly(
        db, user_id=job.user_id, model_id=job.model_id, topic_slug=job.topic_slug
    )


def run_bridge_job(db: Session, job: BridgeJob) -> None:
    """Execute one claimed bridge job to a terminal state. Mirrors
    worker.execute's contract: every failure lands in the job row."""
    log = ProgressLog(db, job)
    spec = get_spec(job.model_id)
    try:
        if spec is None:
            raise ValueError(f"unknown bridge step: {job.model_id}")

        existing = _get_verdict_row(db, job.topic_slug, job.model_id)
        if existing is not None:
            # Library hit or a re-claimed job whose first run finished the work.
            log.event("verdict already on file — serving it")
            job.status = "succeeded"
            job.finished_at = _utcnow()
            db.commit()
            _remember_search(db, job)
            return

        ledger = SpendLedger(db, job)
        deadline = _Deadline(settings.BRIDGE_RUN_TIMEOUT_SECONDS)

        with span(f"bridge:{job.topic_slug}:{job.model_id}", input=job.topic_input):
            if spec.data_requirement == DataRequirement.INHERITS_VERDICT:
                artefact = _produce_inherited(db, job, spec, ledger, log, deadline)
            else:
                artefact, context = _assess(db, job, spec, ledger, log, deadline)
                critic.check(artefact, spec, context)

        _store_verdict(db, job, job.model_id, artefact)
        log.event(f"verdict: {artefact['verdict'].replace('_', ' ')}", stage="done")
        job.status = "succeeded"
    except (BudgetExceeded, PipelineTimeout) as exc:
        # The honest partial-evidence failure — the ceilings did their job.
        logger.warning("job %s stopped by guardrail: %s", job.id, exc)
        _rollback_quietly(db)
        log.event(f"stopped: {exc}")
        job.status = "failed"
        job.error = str(exc)
    except critic.CriticError as exc:
        # A grounding assertion failed: pipeline bug, never a softened verdict.
        logger.error("job %s critic failure: %s", job.id, exc)
        _rollback_quietly(db)
        job.status = "failed"
        job.error = f"internal consistency check failed (pipeline bug): {exc}"
    except Exception as exc:  # noqa: BLE001 — must land in the row, not escape mid-loop
        logger.exception("job %s crashed", job.id)
        # A failed flush leaves the session pending-rollback; without this, the
        # status write below would raise INSIDE the handler and the failure
        # would never land on the row. A genuinely dropped connection makes the
        # rollback itself raise — that propagates to the drain loop, whose
        # reset_session recovery exists for exactly that case.
        _rollback_quietly(db)
        job.status = "failed"
        job.error = f"feasibility run failed unexpectedly: {exc}"

    job.finished_at = _utcnow()
    db.commit()
    if job.status == "succeeded":
        # After the commit, never before: the verdict and the terminal status are
        # what the student came for, and neither may be put at risk by a list
        # entry. record_search_quietly swallows its own failures for the same
        # reason.
        _remember_search(db, job)
    logger.info("bridge job %s -> %s (cost $%.4f)", job.id, job.status, job.cost_usd or 0)


def _produce_inherited(db, job, spec: BridgeSpec, ledger, log, deadline) -> dict:
    """step2's path: reuse the upstream step's assessment wholesale — cheaper
    AND more honest than re-running it (§2). Builds the upstream verdict first
    if this topic never ran it."""
    upstream_id = spec.inherits_from
    upstream_spec = get_spec(upstream_id)
    upstream_row = _get_verdict_row(db, job.topic_slug, upstream_id)
    if upstream_row is None:
        log.event(f"no {upstream_id} verdict on file — assessing it first", stage="upstream")
        upstream_artefact, upstream_context = _assess(db, job, upstream_spec, ledger, log, deadline)
        critic.check(upstream_artefact, upstream_spec, upstream_context)
        upstream_row = _store_verdict(db, job, upstream_id, upstream_artefact)
    else:
        log.event(f"inheriting {upstream_id}'s assessment")

    artefact = verdict_mod.build_inherited(upstream_row.verdict, spec, upstream_id)
    critic.check_inherited(artefact, upstream_row.verdict)
    return artefact


def _assess(db, job, spec: BridgeSpec, ledger, log, deadline) -> tuple[dict, dict]:
    """The OWN_ASSESSMENT pass: the architecture diagram, top to bottom."""
    topic = job.topic_input
    pool = _get_or_build_pool(db, job, spec, ledger, log, deadline)
    candidates: list[dict] = pool["candidates"]
    queries: list[str] = list(pool["queries"])
    rejections: dict = {
        "relevance": {"count": len(pool["rejected_relevance"]),
                      "examples": pool["rejected_relevance"]},
        "license": {"count": 0, "examples": []},
        "loadable": {"count": 0, "examples": []},
        "scale": {"count": 0, "examples": []},
        "probe": {"count": 0, "examples": []},
    }
    notes: dict = {}

    survivors = _run_gates(candidates, spec, rejections, notes, log, deadline)

    replan_rounds = 0
    seen = {(c["source"], c["dataset_id"]) for c in candidates}
    while not survivors and replan_rounds < MAX_REPLANS:
        replan_rounds += 1
        deadline.check("replanning")
        summary = ", ".join(
            f"{len(entry['examples'])} rejected: {gate_name}"
            for gate_name, entry in rejections.items()
            if entry["examples"]
        ) or "no candidates found at all"
        log.event(f"all candidates rejected — reformulating (round {replan_rounds})",
                  stage="replanning")
        new_queries = plan_queries(db, ledger, spec, topic,
                                   round_number=replan_rounds, rejection_summary=summary)
        queries.extend(new_queries)
        # Dedupe within the round too — several queries routinely return the
        # same dataset, and the card index's unique key is per dataset.
        fresh_by_key: dict[tuple, dict] = {}
        for candidate in _fan_out_scouts(new_queries, log):
            key = (candidate["source"], candidate["dataset_id"])
            if key not in seen:
                fresh_by_key.setdefault(key, candidate)
        fresh = list(fresh_by_key.values())
        seen.update(fresh_by_key)
        relevant = _judge_all(db, ledger, spec, topic, fresh, rejections, log)
        candidates.extend(relevant)
        card_index.upsert_cards(db, ledger, relevant, spec.modality)
        _update_pool(db, job, spec, queries, candidates, rejections)
        survivors.extend(_run_gates(relevant, spec, rejections, notes, log, deadline))

    context: dict = {
        "pool_candidates": candidates,
        "evidence": {
            "queries": queries,
            "candidates_considered": len(candidates) + rejections["relevance"]["count"],
            "rejections": rejections,
            "replan_rounds": replan_rounds,
            "not_inspected": notes.get("not_inspected", 0),
        },
    }

    if survivors:
        _probe_finalists(db, spec, survivors, rejections, context, log, deadline)
    else:
        deadline.check("api feasibility")
        log.event("no dataset survived the gates — assessing the API route and "
                  "nearest domains", stage="api_path")
        context["api_assessments"] = assess_api_path(topic, spec)
        context["nearest_domain"] = card_index.nearest_domain(
            db, ledger, topic, spec.modality
        )

    log.event("assembling the verdict", stage="assembling")
    artefact = verdict_mod.assemble(db, ledger, spec, topic, context)
    return artefact, context


def _get_or_build_pool(db, job, spec: BridgeSpec, ledger, log, deadline) -> dict:
    """The candidate pool, keyed (topic_slug, MODALITY) — fetched once, shared
    by every step in the modality. A cache hit here is why adding step6 beside
    step5 costs a probe, not forty searches."""
    from backend.models.Bridge import BridgeCandidatePool

    row = db.execute(
        select(BridgeCandidatePool).where(
            BridgeCandidatePool.topic_slug == job.topic_slug,
            BridgeCandidatePool.modality == spec.modality.value,
        )
    ).scalars().first()
    if row is not None:
        log.event(f"reusing the existing candidate pool "
                  f"({len(row.pool['candidates'])} candidates)", stage="scouting")
        return dict(row.pool)

    deadline.check("planning")
    log.event("planning search queries", stage="planning")
    queries = plan_queries(db, ledger, spec, job.topic_input)
    # The topic as typed is always one of the queries — the planner varies the
    # framing, it doesn't get to lose the original.
    topic_query = job.topic_input.strip().lower()
    if topic_query not in queries:
        queries.insert(0, topic_query)
    log.event(f"{len(queries)} searches dispatched", stage="scouting")

    found = _fan_out_scouts(queries, log)
    recalled = card_index.vector_recall(db, ledger, job.topic_input, spec.modality)
    merged: dict[tuple, dict] = {}
    for candidate in [*found, *recalled]:
        merged.setdefault((candidate["source"], candidate["dataset_id"]), candidate)
    candidates_raw = list(merged.values())
    log.event(f"{len(candidates_raw)} distinct candidates found")

    rejections_stub = {"relevance": {"count": 0, "examples": []}}
    relevant = _judge_all(db, ledger, spec, job.topic_input, candidates_raw,
                          rejections_stub, log)
    card_index.upsert_cards(db, ledger, relevant, spec.modality)

    pool = {
        "queries": queries,
        "candidates": relevant,
        "rejected_relevance": rejections_stub["relevance"]["examples"],
    }
    db.add(BridgeCandidatePool(topic_slug=job.topic_slug, modality=spec.modality.value,
                               pool=pool))
    db.commit()
    return pool


def _update_pool(db, job, spec: BridgeSpec, queries, candidates, rejections) -> None:
    from backend.models.Bridge import BridgeCandidatePool

    row = db.execute(
        select(BridgeCandidatePool).where(
            BridgeCandidatePool.topic_slug == job.topic_slug,
            BridgeCandidatePool.modality == spec.modality.value,
        )
    ).scalars().first()
    if row is not None:
        row.pool = {
            "queries": list(queries),
            "candidates": candidates,
            "rejected_relevance": rejections["relevance"]["examples"],
        }
        row.last_verified = _utcnow()
        db.commit()


def _fan_out_scouts(queries: list[str], log) -> list[dict]:
    """Bounded-concurrency keyword search across the active scouts."""
    scouts = active_scouts()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=settings.BRIDGE_SCOUT_CONCURRENCY) as pool:
        futures = [pool.submit(scout.search, query) for scout in scouts for query in queries]
        for future in futures:
            results.extend(future.result())
    return results


def _judge_all(db, ledger, spec, topic, candidates, rejections, log) -> list[dict]:
    """Relevance-judge candidates (site 2's per-hit call). The spend ceiling is
    checked inside every call, so a surprisingly wide pool aborts mid-batch
    rather than in a bill (§14.8) — but a hard cap on how many are judged at
    all is the cheaper control, since this is the one cost that scales with
    pool size. Most-downloaded first, so the cap sheds the obscure tail."""
    ranked = sorted(candidates, key=lambda c: -(c.get("downloads") or 0))
    limit = settings.BRIDGE_MAX_JUDGED_CANDIDATES
    if len(ranked) > limit:
        log.event(f"judging the {limit} most-used of {len(ranked)} candidates")
        ranked = ranked[:limit]

    relevant = []
    for candidate in ranked:
        judgment = judge_relevance(db, ledger, spec, topic, candidate)
        if judgment.relevant:
            relevant.append(candidate)
        else:
            rejections["relevance"]["examples"].append({
                "dataset_id": candidate["dataset_id"],
                "source": candidate["source"],
                "reason": judgment.reason,
            })
    rejections["relevance"]["count"] = len(rejections["relevance"]["examples"])
    if rejections["relevance"]["examples"]:
        log.event(f"{rejections['relevance']['count']} rejected: not actually about the topic")
    return relevant


def _run_gates(candidates: list[dict], spec: BridgeSpec, rejections: dict,
               notes: dict, log, deadline) -> list[tuple[dict, dict]]:
    """Gates 1-3 over candidates, cheapest first. Returns (candidate,
    inspection) survivors.

    Gate 1 (license) runs over EVERY candidate: it is pure string work, so the
    rejection statistics stay complete. Gates 2-3 need an inspection, and the
    two sources cost wildly different amounts to inspect — HuggingFace answers
    from a free API, while Kaggle has no rows endpoint and must DOWNLOAD the
    dataset. So licensed candidates are inspected HuggingFace-first and the
    walk stops once enough have passed, which keeps a seeding run from pulling
    hundreds of Kaggle archives to pick three finalists. Candidates never
    reached are recorded as such rather than counted as rejections.
    """
    survivors: list[tuple[dict, dict]] = []
    counts_before = {k: rejections[k]["count"] for k in ("license", "loadable", "scale")}

    licensed: list[dict] = []
    for candidate in candidates:
        g1 = gate1_license(candidate)
        if g1.passed:
            licensed.append(candidate)
        else:
            _reject(rejections, "license", candidate, g1.reason)

    # Free-to-inspect first, then by popularity within each source.
    licensed.sort(key=lambda c: (c["source"] != "hf", -(c.get("downloads") or 0)))

    for index, candidate in enumerate(licensed):
        if len(survivors) >= MAX_FINALISTS:
            # A note, deliberately NOT a rejection: nothing was judged about
            # these, and filing them under a gate would overstate the evidence.
            notes["not_inspected"] = notes.get("not_inspected", 0) + (len(licensed) - index)
            break
        deadline.check("gates")
        inspection = (
            tools.inspect_hf_dataset(candidate["dataset_id"])
            if candidate["source"] == "hf"
            else tools.inspect_kaggle_dataset(candidate)
        )
        g2 = gate2_loadable(inspection)
        if not g2.passed:
            _reject(rejections, "loadable", candidate, g2.reason)
            continue
        g3 = gate3_scale(inspection, spec.modality)
        if not g3.passed:
            _reject(rejections, "scale", candidate, g3.reason)
            continue
        if g3.reason != "scale ok":
            inspection["scale_note"] = g3.reason
        survivors.append((candidate, inspection))

    for gate_name in ("license", "loadable", "scale"):
        newly = rejections[gate_name]["count"] - counts_before[gate_name]
        if newly:
            log.event(f"{newly} rejected: {gate_name}")
    if survivors:
        log.event(f"{len(survivors)} candidate(s) passed all gates", stage="gating")
    return survivors


def _reject(rejections: dict, gate_name: str, candidate: dict, reason: str) -> None:
    rejections[gate_name]["examples"].append({
        "dataset_id": candidate["dataset_id"],
        "source": candidate["source"],
        "reason": reason,
    })
    rejections[gate_name]["count"] = len(rejections[gate_name]["examples"])


def _probe_finalists(db, spec: BridgeSpec, survivors, rejections, context,
                     log, deadline) -> None:
    """Gate 4. Chooses the cited dataset and (when the spec has a probe) the
    measured fit. HF finalists first — their rows come from a free API; a large
    Kaggle candidate would need a download to probe."""
    finalists = sorted(
        survivors,
        key=lambda pair: (pair[0]["source"] != "hf", -(pair[0].get("downloads") or 0)),
    )[:MAX_FINALISTS]

    if spec.probe is None:
        candidate, inspection = finalists[0]
        context["dataset"] = candidate
        context["inspection"] = inspection
        context["probe_report"] = None
        context["difficulty"] = score_difficulty(spec, inspection.get("stats", {}))
        log.event("no probe at this level — reporting gates and corpus statistics",
                  stage="probing")
        return

    log.event(f"probing {len(finalists)} finalist(s)", stage="probing")
    from backend.services.bridge.probes.harness import run_probe

    reports: list[tuple[dict, dict, dict]] = []
    for candidate, inspection in finalists:
        deadline.check("probing")
        rows = _rows_for_probe(candidate, inspection, spec.probe.row_cap)
        report = run_probe(spec, rows)
        reports.append((candidate, inspection, report))
        log.event(f"{candidate['dataset_id']}: probe {report['outcome']}")
        if report["outcome"] == ProbeOutcome.PASS.value:
            break

    by_outcome = {outcome: next(
        (r for r in reports if r[2]["outcome"] == outcome), None
    ) for outcome in ("pass", "unconfirmed", "fail")}
    chosen = by_outcome["pass"] or by_outcome["unconfirmed"] or by_outcome["fail"]
    candidate, inspection, report = chosen

    for other_candidate, _, other_report in reports:
        if other_report["outcome"] == ProbeOutcome.FAIL.value and other_candidate is not candidate:
            _reject(rejections, "probe", other_candidate, other_report["reason"])

    context["dataset"] = candidate
    context["inspection"] = inspection
    context["probe_report"] = report
    context["difficulty"] = score_difficulty(spec, inspection.get("stats", {}))


def _rows_for_probe(candidate: dict, inspection: dict, row_cap: int) -> list[dict]:
    if candidate["source"] == "hf":
        return tools.fetch_hf_rows(
            candidate["dataset_id"], inspection["config"], inspection["split"], row_cap
        )
    return tools.fetch_kaggle_rows(candidate["dataset_id"], count=row_cap)
