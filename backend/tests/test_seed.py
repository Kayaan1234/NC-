"""The content seed pipeline: manifest -> DB (idempotent upsert), and the roadmap
feed shape it produces on GET /users/me/dashboard.

Rollout is incremental: Rung 0 ("The single neuron") is authored with one
exercise; Rungs 1-9 are "COMING SOON" placeholders with no exercises. The
dashboard must therefore show Rung 0 unlocked (lit) and the rest locked (unlit)."""

from uuid import UUID

from sqlalchemy import select

from backend import models
from backend.seed.manifest import COMING_SOON, ExerciseSeed
from backend.seed.seeder import _upsert_exercise, seed
from backend.tests.helpers import auth_header, register_and_verify


def _counts(db) -> tuple[int, int]:
    rungs = db.execute(select(models.Rungs)).scalars().all()
    exercises = db.execute(select(models.Exercise)).scalars().all()
    return len(rungs), len(exercises)


def test_seed_populates_manifest(db_session):
    seed(db_session)
    db_session.commit()

    assert _counts(db_session) == (10, 1)  # 10 rungs, only Rung 0 authored

    r0 = db_session.execute(
        select(models.Rungs).where(models.Rungs.number == 0)
    ).scalar_one()
    assert r0.title == "The single neuron"
    assert r0.slug == "the-single-neuron"
    assert len(r0.exercises) == 1

    ex = r0.exercises[0]
    assert ex.order_index == 0
    assert ex.slug == "essential-maths"
    assert ex.read_only is False  # a normal, solvable exercise
    # starter/solution are read from the real .hpp files on disk, not inlined.
    assert ex.starter_code.startswith("#pragma once")
    assert "std::exp(-x)" in ex.model_solution  # the sigmoid implementation

    placeholders = db_session.execute(
        select(models.Rungs).where(models.Rungs.number != 0)
    ).scalars().all()
    assert len(placeholders) == 9
    assert all(r.title == COMING_SOON for r in placeholders)
    assert all(len(r.exercises) == 0 for r in placeholders)


def test_seed_is_idempotent(db_session):
    seed(db_session)
    db_session.commit()
    first = _counts(db_session)

    # Re-running must upsert in place — no duplicates, no unique-constraint errors.
    seed(db_session)
    db_session.commit()
    second = _counts(db_session)

    assert first == second == (10, 1)


def test_seed_read_only_exercise_has_null_starter(db_session):
    """A read-only exercise ships only the runnable solution: the seeder writes
    read_only=True and a NULL starter_code (exercising the now-nullable column)
    while model_solution is still populated from the .hpp on disk."""
    rung = models.Rungs(number=0, slug="r0", title="R0", description="d")
    db_session.add(rung)
    db_session.flush()

    ro = ExerciseSeed(
        order_index=1,
        slug="demo-readonly",
        title="Runnable demo",
        prompt="Read the reference implementation.",
        solution_ref="Rung0/Ex0Solution.hpp",  # reuse an existing .hpp; no starter_ref
        read_only=True,
    )
    row = _upsert_exercise(db_session, rung.id, ro)
    db_session.commit()

    assert row.read_only is True
    assert row.starter_code is None
    assert row.model_solution.strip() != ""


def test_dashboard_reflects_seed(client, sent_emails, db_session):
    seed(db_session)
    db_session.commit()

    user = register_and_verify(client, sent_emails, email="roadmap@example.com")
    resp = client.get("/users/me/dashboard", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert [r["number"] for r in body["rungs"]] == list(range(10))
    assert body["current_rung_number"] == 0

    rungs = {r["number"]: r for r in body["rungs"]}
    assert rungs[0]["status"] == "unlocked"
    assert rungs[0]["title"] == "The single neuron"
    assert rungs[0]["exercises_total"] == 1
    for n in range(1, 10):
        assert rungs[n]["status"] == "locked"
        assert rungs[n]["title"] == COMING_SOON
        assert rungs[n]["exercises_total"] == 0


def test_empty_rung_stays_locked_even_after_prior_completed(client, sent_emails, db_session):
    """A COMING SOON rung (no exercises) must not auto-unlock once the prior rung
    is completed — the total>0 guard in get_user_dashboard. Without it this rung
    would report "unlocked" despite having no authored content."""
    user = register_and_verify(client, sent_emails, email="guard@example.com")
    uid = UUID(user["user_id"])

    r0 = models.Rungs(number=0, slug="r0", title="R0", description="d")
    db_session.add(r0)
    db_session.flush()
    ex = models.Exercise(
        rung_id=r0.id, order_index=0, slug="r0e0", title="e",
        prompt="p", starter_code="s", model_solution="m",
    )
    db_session.add(ex)
    db_session.flush()
    db_session.add(models.Rungs(number=1, slug="r1", title=COMING_SOON, description="d"))
    db_session.add(models.UserExerciseProgress(
        user_id=uid, exercise_id=ex.id, status=models.ProgressStatus.COMPLETED,
    ))
    db_session.commit()

    resp = client.get("/users/me/dashboard", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rungs = {r["number"]: r for r in body["rungs"]}

    assert rungs[0]["status"] == "completed"
    assert rungs[1]["status"] == "locked"  # would be "unlocked" without the guard
    assert body["current_rung_number"] is None
