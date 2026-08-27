"""The bridge CLI: run one verdict, seed the library, review and promote.

    python -m backend.services.bridge.cli run --topic "premier league results" --model step1
    python -m backend.services.bridge.cli seed --topics backend/services/bridge/seed_topics.json --steps step0,step1,step3
    python -m backend.services.bridge.cli list-drafts
    python -m backend.services.bridge.cli promote premier-league-results step1

Runs the pipeline in-process (no worker needed), writing the same job rows and
verdict rows the live path writes — seed jobs carry source='seed' and no user,
so their spend is ledgered but they never occupy anyone's active slot.

A conscious deviation from bridge-plan-v3.md §14.7, recorded here and in
BRIDGE_SERVICES.md: seeding runs the SYNCHRONOUS pipeline per cell rather than
the Batch API. Stage-wise batching across topics would be a second orchestrator
to save ~50% of an already-small number (30 cells ≈ a dollar; pool sharing
across the three tabular steps already removes two-thirds of the search cost).
Revisit if the library grows an order of magnitude.
"""

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from backend.core.config import settings
from backend.database import SessionLocal
from backend.models.Bridge import (
    BridgeJob,
    BridgeJobSource,
    BridgeJobStatus,
    BridgeVerdict,
    BridgeVerdictStatus,
)
from backend.models.TrainingJob import utcnow
from backend.services.bridge import tracing
from backend.services.bridge.llm import SpendLedger
from backend.services.bridge.pipeline import run_bridge_job
from backend.services.bridge.registry import BRIDGE_SPECS, check_bridge_registry
from backend.services.bridge.slug import slugify_topic
from backend.services.bridge.verdict import write_summary

logger = logging.getLogger("backend.bridge.cli")


def _require_keys() -> None:
    missing = [k for k in ("ANTHROPIC_API_KEY", "VOYAGER_API_KEY") if not getattr(settings, k)]
    if missing:
        sys.exit(f"cannot run the pipeline: {', '.join(missing)} not set in backend/.env")


def _run_cell(db, topic: str, model_id: str, force: bool) -> BridgeJob:
    slug = slugify_topic(topic)
    if force:
        existing = db.execute(
            select(BridgeVerdict).where(
                BridgeVerdict.topic_slug == slug, BridgeVerdict.model_id == model_id
            )
        ).scalars().first()
        if existing is not None:
            db.delete(existing)
            db.commit()
            print(f"deleted existing verdict for ({slug}, {model_id})")

    job = BridgeJob(
        user_id=None,
        topic_input=topic.strip(),
        topic_slug=slug,
        model_id=model_id,
        source=BridgeJobSource.SEED.value,
        status=BridgeJobStatus.RUNNING.value,
        started_at=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    run_bridge_job(db, job)
    return job


def cmd_run(args) -> int:
    _require_keys()
    if args.model not in BRIDGE_SPECS:
        sys.exit(f"unknown step {args.model!r}; one of {sorted(BRIDGE_SPECS)}")
    db = SessionLocal()
    try:
        job = _run_cell(db, args.topic, args.model, args.force)
        print(f"\njob {job.id}: {job.status} (cost ${job.cost_usd or 0})")
        if job.error:
            print(f"error: {job.error}")
            return 1
        row = db.execute(
            select(BridgeVerdict).where(
                BridgeVerdict.topic_slug == job.topic_slug,
                BridgeVerdict.model_id == job.model_id,
            )
        ).scalars().first()
        if row:
            print(json.dumps(row.verdict, indent=2))
        return 0
    finally:
        db.close()
        tracing.flush()


def cmd_seed(args) -> int:
    _require_keys()
    topics = json.loads(Path(args.topics).read_text())
    if not isinstance(topics, list):
        sys.exit("topics file must be a JSON array of topic strings")
    steps = args.steps.split(",")
    unknown = [s for s in steps if s not in BRIDGE_SPECS]
    if unknown:
        sys.exit(f"unknown steps: {unknown}")

    db = SessionLocal()
    total = Decimal("0")
    cap = Decimal(str(args.max_spend))
    try:
        for topic in topics:
            for step in steps:
                slug = slugify_topic(topic)
                existing = db.execute(
                    select(BridgeVerdict).where(
                        BridgeVerdict.topic_slug == slug, BridgeVerdict.model_id == step
                    )
                ).scalars().first()
                if existing is not None:
                    print(f"skip ({slug}, {step}): verdict exists")
                    continue
                if total >= cap:
                    print(f"stopping: seed spend cap ${cap} reached (${total} spent)")
                    return 0
                print(f"=== {topic} @ {step} ===")
                job = _run_cell(db, topic, step, force=False)
                total += Decimal(job.cost_usd or 0)
                print(f"    -> {job.status}, ${job.cost_usd or 0} (total ${total})")
        print(f"\nseeding done: ${total} spent. Review with list-drafts, publish with promote.")
        return 0
    finally:
        db.close()
        tracing.flush()


def cmd_resummarise(args) -> int:
    """Rewrite stored verdicts' one sentence with the current prompt.

    The summary is the only generated prose in an artefact, so a prompt change
    is the one edit that leaves existing verdicts stale. Everything else on the
    page is a record and re-renders itself. Cheap (one small call per verdict),
    and it never touches the records the critic asserts over.
    """
    _require_keys()
    db = SessionLocal()
    total = Decimal("0")
    try:
        rows = db.execute(
            select(BridgeVerdict).order_by(BridgeVerdict.topic_slug, BridgeVerdict.model_id)
        ).scalars().all()
        # One ledger row for the whole batch, so the spend is recorded like any
        # other job rather than vanishing.
        job = BridgeJob(
            user_id=None, topic_input="(re-summarise)", topic_slug="_resummarise",
            model_id="-", source=BridgeJobSource.SEED.value,
            status=BridgeJobStatus.RUNNING.value,
        )
        db.add(job)
        db.commit()
        ledger = SpendLedger(db, job)
        # This batch legitimately exceeds a single verdict's ceiling.
        ledger.ceiling = Decimal(str(args.max_spend))

        for row in rows:
            artefact = dict(row.verdict)
            if artefact.get("inherited_from"):
                continue  # its sentence is derived from upstream, not generated
            before = artefact.get("summary", "")
            sentence = write_summary(db, ledger, artefact)
            row.verdict = artefact
            db.commit()
            if sentence != before:
                print(f"{row.topic_slug} / {row.model_id}\n    {sentence}")
        job.status = BridgeJobStatus.SUCCEEDED.value
        job.finished_at = utcnow()
        db.commit()
        total = Decimal(job.cost_usd or 0)
        print(f"\nre-summarised {len(rows)} verdict(s), ${total}")
        return 0
    finally:
        db.close()
        tracing.flush()


def cmd_list_drafts(args) -> int:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(BridgeVerdict).order_by(BridgeVerdict.topic_slug, BridgeVerdict.model_id)
        ).scalars().all()
        for row in rows:
            marker = "PUB " if row.status == BridgeVerdictStatus.PUBLISHED.value else "draft"
            print(f"[{marker}] {row.topic_slug:40s} {row.model_id:6s} "
                  f"{row.verdict.get('verdict', ''):26s} {row.verdict.get('summary', '')[:70]}")
        return 0
    finally:
        db.close()


def _set_status(topic_slug: str, model_id: str, new_status: str) -> int:
    db = SessionLocal()
    try:
        row = db.execute(
            select(BridgeVerdict).where(
                BridgeVerdict.topic_slug == topic_slug, BridgeVerdict.model_id == model_id
            )
        ).scalars().first()
        if row is None:
            print(f"no verdict for ({topic_slug}, {model_id})")
            return 1
        row.status = new_status
        db.commit()
        print(f"({topic_slug}, {model_id}) -> {new_status}")
        return 0
    finally:
        db.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    check_bridge_registry(require_probe_impls=True)

    parser = argparse.ArgumentParser(prog="bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="one live verdict, printed")
    run_parser.add_argument("--topic", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--force", action="store_true",
                            help="delete any existing verdict for this cell first")
    run_parser.set_defaults(func=cmd_run)

    seed_parser = sub.add_parser("seed", help="run the pipeline over topics x steps")
    seed_parser.add_argument("--topics", required=True, help="JSON array file of topic strings")
    seed_parser.add_argument("--steps", default="step0,step1,step3")
    seed_parser.add_argument("--max-spend", type=float, default=2.00,
                             help="stop seeding once this many dollars are spent (default 2.00)")
    seed_parser.set_defaults(func=cmd_seed)

    drafts_parser = sub.add_parser("list-drafts", help="all verdicts and their review state")
    drafts_parser.set_defaults(func=cmd_list_drafts)

    resum_parser = sub.add_parser(
        "resummarise", help="rewrite every stored verdict's sentence with the current prompt"
    )
    resum_parser.add_argument("--max-spend", type=float, default=0.50)
    resum_parser.set_defaults(func=cmd_resummarise)

    promote_parser = sub.add_parser("promote", help="publish a verdict into the library")
    promote_parser.add_argument("topic_slug")
    promote_parser.add_argument("model_id")
    promote_parser.set_defaults(
        func=lambda a: _set_status(a.topic_slug, a.model_id, BridgeVerdictStatus.PUBLISHED.value)
    )

    demote_parser = sub.add_parser("demote", help="pull a verdict back to draft")
    demote_parser.add_argument("topic_slug")
    demote_parser.add_argument("model_id")
    demote_parser.set_defaults(
        func=lambda a: _set_status(a.topic_slug, a.model_id, BridgeVerdictStatus.DRAFT.value)
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
