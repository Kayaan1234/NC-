"""GET /users/me and GET /users/me/dashboard — the response shapes the SPA
consumes (UserPublic and DashboardOut), including the rung lock/unlock logic."""

from uuid import UUID

from backend import models
from backend.tests.helpers import auth_header, register_and_verify


def test_users_me_returns_userpublic_shape(client, sent_emails):
    user = register_and_verify(client, sent_emails, username="alice", email="alice@example.com")
    resp = client.get("/users/me", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body.keys()) == {"id", "username", "email", "verified"}
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["verified"] is True
    UUID(body["id"])


def test_dashboard_empty_when_no_content(client, sent_emails):
    user = register_and_verify(client, sent_emails)
    resp = client.get("/users/me/dashboard", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"rungs": [], "current_rung_number": None}


def _seed_rung(db, number, slug, title, n_exercises):
    rung = models.Rungs(number=number, slug=slug, title=title, description="d")
    db.add(rung)
    db.flush()
    exercises = []
    for i in range(n_exercises):
        ex = models.Exercise(
            rung_id=rung.id,
            order_index=i,
            slug=f"{slug}-ex{i}",
            title=f"{title} ex{i}",
            prompt="p",
            starter_code="s",
            model_solution="m",
        )
        db.add(ex)
        exercises.append(ex)
    db.flush()
    return rung, exercises


def test_dashboard_shape_and_lock_logic(client, sent_emails, db_session):
    user = register_and_verify(client, sent_emails, email="alice@example.com")
    uid = UUID(user["user_id"])

    # Rung 0: fully completed. Rung 1: partially done (=> current). Rung 2: locked.
    _r0, r0_ex = _seed_rung(db_session, 0, "rung0", "Rung Zero", 2)
    _r1, r1_ex = _seed_rung(db_session, 1, "rung1", "Rung One", 2)
    _seed_rung(db_session, 2, "rung2", "Rung Two", 1)

    for ex in r0_ex:  # complete both of rung 0
        db_session.add(models.UserExerciseProgress(
            user_id=uid, exercise_id=ex.id, status=models.ProgressStatus.COMPLETED
        ))
    db_session.add(models.UserExerciseProgress(  # 1 of 2 in rung 1
        user_id=uid, exercise_id=r1_ex[0].id, status=models.ProgressStatus.COMPLETED
    ))
    db_session.commit()

    resp = client.get("/users/me/dashboard", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["current_rung_number"] == 1
    assert [r["number"] for r in body["rungs"]] == [0, 1, 2]

    rungs = {r["number"]: r for r in body["rungs"]}
    # Every rung carries exactly the RungProgressOut shape.
    assert set(rungs[0].keys()) == {
        "id", "number", "slug", "title", "status", "exercises_completed", "exercises_total"
    }
    assert rungs[0]["status"] == "completed"
    assert rungs[0]["exercises_completed"] == 2 and rungs[0]["exercises_total"] == 2

    assert rungs[1]["status"] == "unlocked"
    assert rungs[1]["exercises_completed"] == 1 and rungs[1]["exercises_total"] == 2

    assert rungs[2]["status"] == "locked"
    assert rungs[2]["exercises_completed"] == 0 and rungs[2]["exercises_total"] == 1
