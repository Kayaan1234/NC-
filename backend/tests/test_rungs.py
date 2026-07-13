"""GET /rungs/{rung_number}/exercises — the per-exercise progress feed the SPA's
rung title page will consume (UserRungProgressResponse).

The exercises table is empty in every environment today, so this endpoint has
never actually run against data. These tests seed content directly to exercise
its logic now and pin the contract so it won't silently break when real
exercises are authored: the response shape, per-user progress, the read-only
flag, the resume pointer (next_incomplete_slug), ordering, empty/unknown rungs,
and the verified-account gate.
"""

from uuid import UUID

from backend import models
from backend.tests.helpers import auth_header, login, register, register_and_verify


def _seed_rung(db, number, slug, title, exercises):
    """Seed a rung and its exercises.

    `exercises` is an iterable of (order_index, slug, read_only). Returns
    (rung, {slug: Exercise}) so tests can attach progress rows by slug.
    """
    rung = models.Rungs(number=number, slug=slug, title=title, description="d")
    db.add(rung)
    db.flush()
    made: dict[str, models.Exercise] = {}
    for order_index, ex_slug, read_only in exercises:
        ex = models.Exercise(
            rung_id=rung.id,
            order_index=order_index,
            slug=ex_slug,
            title=ex_slug.replace("-", " ").title(),
            prompt="p",
            starter_code="s",
            model_solution="m",
            read_only=read_only,
        )
        db.add(ex)
        made[ex_slug] = ex
    db.flush()
    return rung, made


def _set_progress(db, uid, exercise, status):
    db.add(models.UserExerciseProgress(user_id=uid, exercise_id=exercise.id, status=status))


def test_unknown_rung_returns_404(client, sent_emails):
    user = register_and_verify(client, sent_emails)
    resp = client.get("/rungs/99/exercises", headers=auth_header(user["access_token"]))
    assert resp.status_code == 404, resp.text


def test_empty_rung_returns_empty_list(client, sent_emails, db_session):
    """A seeded-but-exerciseless rung (today's real state) is 200 + empty, NOT 404."""
    user = register_and_verify(client, sent_emails)
    _seed_rung(db_session, 0, "the-single-neuron", "The single neuron", [])
    db_session.commit()

    resp = client.get("/rungs/0/exercises", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"exercises": [], "next_incomplete_slug": None}


def test_shape_progress_readonly_and_resume_pointer(client, sent_emails, db_session):
    user = register_and_verify(client, sent_emails)
    uid = UUID(user["user_id"])
    _rung, ex = _seed_rung(
        db_session,
        0,
        "the-single-neuron",
        "The single neuron",
        [(0, "essential-maths", False), (1, "forward-prop", False), (2, "grad-check", True)],
    )
    _set_progress(db_session, uid, ex["essential-maths"], models.ProgressStatus.COMPLETED)
    _set_progress(db_session, uid, ex["forward-prop"], models.ProgressStatus.IN_PROGRESS)
    # grad-check has no progress row => not_started.
    db_session.commit()

    resp = client.get("/rungs/0/exercises", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    items = {e["slug"]: e for e in body["exercises"]}
    assert set(items["essential-maths"].keys()) == {
        "id", "slug", "title", "order_index", "status", "read_only"
    }
    # id is a UUID (the schema previously mistyped it as int).
    UUID(items["essential-maths"]["id"])

    assert items["essential-maths"]["status"] == "completed"
    assert items["forward-prop"]["status"] == "in_progress"
    assert items["grad-check"]["status"] == "not_started"

    assert items["grad-check"]["read_only"] is True
    assert items["essential-maths"]["read_only"] is False

    # Resume point = first exercise (in order) that isn't completed.
    assert body["next_incomplete_slug"] == "forward-prop"


def test_all_completed_has_no_resume_pointer(client, sent_emails, db_session):
    user = register_and_verify(client, sent_emails)
    uid = UUID(user["user_id"])
    _rung, ex = _seed_rung(
        db_session, 0, "rung0", "Rung Zero", [(0, "a", False), (1, "b", False)]
    )
    _set_progress(db_session, uid, ex["a"], models.ProgressStatus.COMPLETED)
    _set_progress(db_session, uid, ex["b"], models.ProgressStatus.COMPLETED)
    db_session.commit()

    resp = client.get("/rungs/0/exercises", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(e["status"] == "completed" for e in body["exercises"])
    assert body["next_incomplete_slug"] is None


def test_exercises_ordered_by_order_index(client, sent_emails, db_session):
    """Seed out of insertion order; the endpoint must sort by order_index so the
    resume pointer and the SPA's list are deterministic."""
    user = register_and_verify(client, sent_emails)
    _seed_rung(
        db_session,
        0,
        "rung0",
        "Rung Zero",
        [(2, "third", False), (0, "first", False), (1, "second", False)],
    )
    db_session.commit()

    resp = client.get("/rungs/0/exercises", headers=auth_header(user["access_token"]))
    body = resp.json()
    assert [e["order_index"] for e in body["exercises"]] == [0, 1, 2]
    assert [e["slug"] for e in body["exercises"]] == ["first", "second", "third"]
    assert body["next_incomplete_slug"] == "first"


def test_progress_is_scoped_to_the_requesting_user(client_factory, sent_emails, db_session):
    """The user_id filter on the join must not leak one user's completions to
    another — otherwise every learner would see the first learner's progress."""
    alice_client = client_factory()
    alice = register_and_verify(
        alice_client, sent_emails, username="alice", email="alice@example.com"
    )
    bob_client = client_factory()
    bob = register_and_verify(bob_client, sent_emails, username="bob", email="bob@example.com")

    _rung, ex = _seed_rung(
        db_session, 0, "rung0", "Rung Zero", [(0, "a", False), (1, "b", False)]
    )
    _set_progress(db_session, UUID(alice["user_id"]), ex["a"], models.ProgressStatus.COMPLETED)
    db_session.commit()

    a_body = alice_client.get("/rungs/0/exercises", headers=auth_header(alice["access_token"])).json()
    b_body = bob_client.get("/rungs/0/exercises", headers=auth_header(bob["access_token"])).json()

    a_status = {e["slug"]: e["status"] for e in a_body["exercises"]}
    b_status = {e["slug"]: e["status"] for e in b_body["exercises"]}

    assert a_status == {"a": "completed", "b": "not_started"}
    assert a_body["next_incomplete_slug"] == "b"
    # Bob has done nothing: 'a' is not_started for him and is his resume point.
    assert b_status == {"a": "not_started", "b": "not_started"}
    assert b_body["next_incomplete_slug"] == "a"


def test_requires_authenticated_and_verified_user(client, sent_emails):
    # No token at all -> 401.
    assert client.get("/rungs/0/exercises").status_code == 401

    # Registered but NOT verified -> 403 (the gate fires before the route body,
    # so no seeded rung is needed).
    register(client, username="dan", email="dan@example.com")
    token = login(client, email="dan@example.com").json()["access_token"]
    resp = client.get("/rungs/0/exercises", headers=auth_header(token))
    assert resp.status_code == 403, resp.text
