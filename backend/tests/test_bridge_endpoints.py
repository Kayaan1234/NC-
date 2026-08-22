"""Integration tests for /bridge: the library, the live-path guards, and the
run lifecycle — everything the router decides, with the worker out of the
picture (a queued job just stays queued here).
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from backend.core.config import settings
from backend.core.limiter import limiter
from backend.models.Bridge import (
    BridgeJob,
    BridgeJobSource,
    BridgeJobStatus,
    BridgeRecentSearch,
    BridgeVerdict,
    BridgeVerdictStatus,
)
from backend.models.TrainingJob import utcnow
from backend.tests.helpers import auth_header, register_and_verify

TOPIC = "premier league football results"


# Both fixtures set the flag EXPLICITLY rather than leaning on its default:
# backend/.env is a developer's file and may legitimately have the feature
# switched on, which must not decide what these tests assert.
@pytest.fixture()
def bridge_enabled(monkeypatch):
    monkeypatch.setattr(settings, "BRIDGE_ENABLED", True)


@pytest.fixture()
def bridge_disabled(monkeypatch):
    monkeypatch.setattr(settings, "BRIDGE_ENABLED", False)


@pytest.fixture()
def verified(client, outbox):
    return register_and_verify(client, outbox)


def _post_run(client, token, topic=TOPIC, model_id="step1"):
    return client.post(
        "/bridge/runs",
        json={"topic": topic, "model_id": model_id},
        headers=auth_header(token),
    )


def _verdict_row(topic_slug="premier-league-football-results", model_id="step1",
                 status=BridgeVerdictStatus.DRAFT.value):
    return BridgeVerdict(
        topic_slug=topic_slug,
        model_id=model_id,
        topic_display=TOPIC,
        verdict={"verdict": "buildable_now", "summary": "a fine dataset exists"},
        status=status,
    )


class TestSpecs:
    def test_all_ten_steps_served_in_ladder_order(self, client, verified):
        response = client.get("/bridge/specs", headers=auth_header(verified["access_token"]))
        assert response.status_code == 200
        specs = response.json()
        assert [s["ordinal"] for s in specs] == list(range(10))

    def test_availability_is_derived_from_the_model_registry(self, client, verified):
        specs = {s["model_id"]: s for s in client.get(
            "/bridge/specs", headers=auth_header(verified["access_token"])
        ).json()}
        assert specs["step0"]["available"] and specs["step1"]["available"]
        assert not specs["step9"]["available"]  # describable, not yet trainable

    def test_requires_auth(self, client):
        assert client.get("/bridge/specs").status_code == 401


class TestStartRun:
    def test_disabled_means_503_not_a_zombie_job(self, client, verified, bridge_disabled):
        response = _post_run(client, verified["access_token"])
        assert response.status_code == 503

    def test_unknown_step_is_404(self, client, verified, bridge_enabled):
        response = _post_run(client, verified["access_token"], model_id="step99")
        assert response.status_code == 404

    def test_unusable_topic_is_422(self, client, verified, bridge_enabled):
        response = _post_run(client, verified["access_token"], topic="!!!")
        assert response.status_code == 422

    def test_accepts_and_queues(self, client, verified, bridge_enabled):
        response = _post_run(client, verified["access_token"])
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["library_hit"] is False
        assert body["job"]["status"] == BridgeJobStatus.QUEUED.value
        assert body["topic_slug"] == "premier-league-football-results"

    def test_one_active_run_per_user(self, client, verified, bridge_enabled):
        assert _post_run(client, verified["access_token"]).status_code == 202
        second = _post_run(client, verified["access_token"], topic="chess game outcomes")
        assert second.status_code == 409

    def test_rate_limit_backstops_the_quota(self, client, verified, bridge_enabled):
        # The suite runs with the limiter inert (see conftest._reset_rate_limiter);
        # this test opts back in, the same way test_auth_rate_limit.py does.
        limiter.reset()
        limiter.enabled = True
        try:
            token = verified["access_token"]
            statuses = [_post_run(client, token, topic=f"topic number {i}").status_code
                        for i in range(4)]
            # 1st queues, 2nd-3rd trip the active-job quota, 4th trips RATE_LIMIT_BRIDGE.
            assert statuses == [202, 409, 409, 429]
        finally:
            limiter.reset()
            limiter.enabled = False

    def test_library_hit_costs_nothing_and_works_even_while_disabled(
        self, client, verified, db_session, bridge_disabled
    ):
        db_session.add(_verdict_row())
        db_session.commit()
        response = _post_run(client, verified["access_token"])
        assert response.status_code == 202
        body = response.json()
        assert body["library_hit"] is True and body["job"] is None
        assert db_session.query(BridgeJob).count() == 0

    def test_daily_cap_refuses_with_429(self, client, verified, bridge_enabled, monkeypatch):
        monkeypatch.setattr(settings, "BRIDGE_DAILY_SPEND_CAP_USD", 0.0)
        response = _post_run(client, verified["access_token"])
        assert response.status_code == 429
        assert "budget" in response.json()["detail"]

    def test_seeding_spend_does_not_consume_the_daily_cap(
        self, client, verified, bridge_enabled, db_session, monkeypatch
    ):
        """Stocking the library from the CLI must not lock learners out. A seed
        session legitimately costs several times the daily cap."""
        monkeypatch.setattr(settings, "BRIDGE_DAILY_SPEND_CAP_USD", 1.00)
        db_session.add(
            BridgeJob(
                user_id=None,
                topic_input="seeded topic",
                topic_slug="seeded-topic",
                model_id="step0",
                source=BridgeJobSource.SEED.value,
                status=BridgeJobStatus.SUCCEEDED.value,
                cost_usd=Decimal("50.00"),
            )
        )
        db_session.commit()
        assert _post_run(client, verified["access_token"]).status_code == 202


class TestRuns:
    def test_own_runs_listed_and_pollable(self, client, verified, bridge_enabled):
        created = _post_run(client, verified["access_token"]).json()["job"]
        token = verified["access_token"]
        listed = client.get("/bridge/runs", headers=auth_header(token)).json()
        assert [j["id"] for j in listed] == [created["id"]]
        polled = client.get(f"/bridge/runs/{created['id']}", headers=auth_header(token))
        assert polled.status_code == 200
        assert polled.json()["queue_position"] == 0

    def test_someone_elses_run_is_indistinguishable_from_none(
        self, client, outbox, verified, bridge_enabled
    ):
        created = _post_run(client, verified["access_token"]).json()["job"]
        other = register_and_verify(client, outbox, username="bob", email="bob@example.com")
        response = client.get(
            f"/bridge/runs/{created['id']}", headers=auth_header(other["access_token"])
        )
        assert response.status_code == 404


def _queued_job(user_id, topic="stuck topic", age_seconds=0):
    """A job in the queue, optionally aged. Built directly rather than through
    the API because the point is a queue nothing is draining."""
    return BridgeJob(
        user_id=user_id,
        topic_input=topic,
        topic_slug=topic.replace(" ", "-"),
        model_id="step1",
        source=BridgeJobSource.LIVE.value,
        status=BridgeJobStatus.QUEUED.value,
        created_at=utcnow() - timedelta(seconds=age_seconds),
    )


class TestStalledQueue:
    """A job nothing ever claims.

    bridge_drain.reclaim_stale only rescues jobs that reached RUNNING and went
    quiet. One that is never claimed has no heartbeat to go quiet, so its only
    tell is the age of the queue's head — and until it grew one, it rendered as
    a cheerful "starting up" for as long as anyone was willing to wait.
    """

    def test_a_queue_that_is_moving_is_not_stalled(self, client, verified, bridge_enabled):
        job = _post_run(client, verified["access_token"]).json()["job"]
        assert job["stalled"] is False

    def test_an_unclaimed_job_says_so(self, client, verified, db_session, monkeypatch):
        monkeypatch.setattr(settings, "BRIDGE_JOB_QUEUE_STALE_SECONDS", 300)
        db_session.add(_queued_job(verified["user_id"], age_seconds=600))
        db_session.commit()
        listed = client.get("/bridge/runs", headers=auth_header(verified["access_token"])).json()
        assert listed[0]["stalled"] is True

    def test_everyone_behind_a_stuck_head_is_stalled_too(
        self, client, outbox, verified, db_session, monkeypatch
    ):
        """The one a per-job age or queue_position rule gets wrong.

        Second in line has queue_position 1 and was created seconds ago, so both
        of those readings call it healthy. It is not: nothing is draining, and
        the head of the queue is the only thing that knows.
        """
        monkeypatch.setattr(settings, "BRIDGE_JOB_QUEUE_STALE_SECONDS", 300)
        bob = register_and_verify(client, outbox, username="bob", email="bob@example.com")
        db_session.add(_queued_job(verified["user_id"], age_seconds=600))
        db_session.add(_queued_job(bob["user_id"], topic="just asked", age_seconds=1))
        db_session.commit()

        listed = client.get("/bridge/runs", headers=auth_header(bob["access_token"])).json()
        assert listed[0]["queue_position"] == 1     # behind someone
        assert listed[0]["stalled"] is True         # ...and that someone is going nowhere


class TestCancelRun:
    def test_a_queued_run_can_be_called_off(self, client, verified, db_session):
        db_session.add(_queued_job(verified["user_id"]))
        db_session.commit()
        run_id = client.get(
            "/bridge/runs", headers=auth_header(verified["access_token"])
        ).json()[0]["id"]

        response = client.delete(f"/bridge/runs/{run_id}", headers=auth_header(verified["access_token"]))
        assert response.status_code == 200
        assert response.json()["status"] == BridgeJobStatus.CANCELLED.value

    def test_cancelling_frees_the_active_slot(self, client, verified, db_session, bridge_enabled):
        """The property the student actually cares about: they can search again."""
        assert _post_run(client, verified["access_token"]).status_code == 202
        assert _post_run(client, verified["access_token"], topic="chess openings").status_code == 409

        run_id = client.get(
            "/bridge/runs", headers=auth_header(verified["access_token"])
        ).json()[0]["id"]
        client.delete(f"/bridge/runs/{run_id}", headers=auth_header(verified["access_token"]))

        assert _post_run(client, verified["access_token"], topic="chess openings").status_code == 202

    def test_a_running_job_is_refused(self, client, verified, db_session):
        """Cancelling mid-run would abandon a worker that is already spending
        money on it — the same reason train.py's clear only touches terminal jobs."""
        job = _queued_job(verified["user_id"])
        job.status = BridgeJobStatus.RUNNING.value
        db_session.add(job)
        db_session.commit()
        run_id = str(job.id)

        response = client.delete(f"/bridge/runs/{run_id}", headers=auth_header(verified["access_token"]))
        assert response.status_code == 409

    def test_someone_elses_run_is_indistinguishable_from_none(
        self, client, outbox, verified, db_session
    ):
        db_session.add(_queued_job(verified["user_id"]))
        db_session.commit()
        run_id = client.get(
            "/bridge/runs", headers=auth_header(verified["access_token"])
        ).json()[0]["id"]

        other = register_and_verify(client, outbox, username="bob", email="bob@example.com")
        response = client.delete(f"/bridge/runs/{run_id}", headers=auth_header(other["access_token"]))
        assert response.status_code == 404


class TestVerdictsAndLibrary:
    def test_missing_verdict_is_404(self, client, verified):
        response = client.get(
            "/bridge/verdicts/nothing-here/step1", headers=auth_header(verified["access_token"])
        )
        assert response.status_code == 404

    def test_stored_verdict_is_served(self, client, verified, db_session):
        db_session.add(_verdict_row())
        db_session.commit()
        response = client.get(
            "/bridge/verdicts/premier-league-football-results/step1",
            headers=auth_header(verified["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["verdict"]["verdict"] == "buildable_now"

    def test_library_lists_published_only(self, client, verified, db_session):
        db_session.add(_verdict_row())  # draft
        db_session.add(_verdict_row(topic_slug="chess-game-outcomes",
                                    status=BridgeVerdictStatus.PUBLISHED.value))
        db_session.commit()
        entries = client.get(
            "/bridge/library", headers=auth_header(verified["access_token"])
        ).json()
        assert [e["topic_slug"] for e in entries] == ["chess-game-outcomes"]


def _lookup(client, token, topic, model_id="step1"):
    """The free half of searching: POST /bridge/recent."""
    return client.post(
        "/bridge/recent",
        json={"topic": topic, "model_id": model_id},
        headers=auth_header(token),
    )


def _recent_slugs(client, token, model_id="step1"):
    query = f"?model_id={model_id}" if model_id else ""
    return [
        e["topic_slug"]
        for e in client.get(f"/bridge/recent{query}", headers=auth_header(token)).json()
    ]


class TestRecentSearches:
    """The student's own half of the finder.

    Everything else in the bridge is global — one verdict per (topic, step),
    shared by everyone. This is the one per-user surface, and it exists because a
    finished search previously had nowhere to land: live runs store DRAFT
    verdicts, the shelf lists PUBLISHED only, and the progress panel unmounts the
    instant a run stops being queued or running.
    """

    def test_a_new_student_has_no_searches(self, client, verified):
        assert _recent_slugs(client, verified["access_token"]) == []

    def test_requires_auth(self, client):
        assert client.get("/bridge/recent").status_code == 401
        assert client.post("/bridge/recent", json={"topic": TOPIC, "model_id": "step1"}).status_code == 401

    def test_a_hit_is_remembered_without_queueing_anything(
        self, client, verified, db_session, bridge_enabled
    ):
        db_session.add(_verdict_row())
        db_session.commit()
        response = _lookup(client, verified["access_token"], TOPIC)
        assert response.status_code == 200
        assert response.json() == {
            "topic_slug": "premier-league-football-results",
            "exists": True,
        }
        assert _recent_slugs(client, verified["access_token"]) == [
            "premier-league-football-results"
        ]
        # The whole point of the second endpoint: no job, so no spend and no
        # claim on the one-active-run slot.
        assert db_session.query(BridgeJob).count() == 0

    def test_a_miss_records_nothing(self, client, verified, bridge_enabled):
        response = _lookup(client, verified["access_token"], "nobody has checked this")
        assert response.json()["exists"] is False
        # A row here would draw a card with nothing behind it, and would evict a
        # real result to make room for it.
        assert _recent_slugs(client, verified["access_token"]) == []

    def test_unknown_step_is_404_and_unusable_topic_is_422(self, client, verified):
        assert _lookup(client, verified["access_token"], TOPIC, model_id="step99").status_code == 404
        assert _lookup(client, verified["access_token"], "!!!").status_code == 422

    def test_one_topic_however_it_is_typed(self, client, verified, db_session):
        """The slug is the cache key, so it has to be the list key too —
        otherwise one verdict shows up as three separate searches."""
        db_session.add(_verdict_row(topic_slug="wine-quality"))
        db_session.commit()
        token = verified["access_token"]
        for typed in ("wine quality", "Wine  Quality!", "  WINE-quality  "):
            assert _lookup(client, token, typed).json()["topic_slug"] == "wine-quality"
        assert _recent_slugs(client, token) == ["wine-quality"]

    def test_remembered_even_while_runs_are_disabled(
        self, client, verified, db_session, bridge_disabled
    ):
        """Looking something up off the shelf costs nothing, so it does not care
        whether the machine that performs runs is switched on."""
        db_session.add(_verdict_row())
        db_session.commit()
        assert _lookup(client, verified["access_token"], TOPIC).json()["exists"] is True
        assert _recent_slugs(client, verified["access_token"]) == [
            "premier-league-football-results"
        ]

    def test_a_fourth_lookup_is_not_rate_limited(self, client, verified, db_session):
        """The regression test for the bug this feature was built on top of.

        RATE_LIMIT_BRIDGE is 3/hour and its decorator sits OUTSIDE the POST
        /bridge/runs handler, so it counts a request before the handler can
        discover the answer was already cached and cost nothing. Routing free
        lookups through there made the fourth search in an hour a 429 — which is
        exactly the "search a fourth topic, watch the oldest fall off" flow the
        list is for. Note this test only means anything with the limiter switched
        back on; the suite runs with it inert.
        """
        topics = ["wine quality", "chess openings", "birdsong", "air quality"]
        for topic in topics:
            db_session.add(_verdict_row(topic_slug=topic.replace(" ", "-")))
        db_session.commit()

        limiter.reset()
        limiter.enabled = True
        try:
            token = verified["access_token"]
            statuses = [_lookup(client, token, topic).status_code for topic in topics]
            assert statuses == [200, 200, 200, 200]
        finally:
            limiter.reset()
            limiter.enabled = False

    def test_a_fourth_search_replaces_the_oldest(self, client, verified, db_session):
        topics = ["wine quality", "chess openings", "birdsong", "air quality"]
        for topic in topics:
            db_session.add(_verdict_row(topic_slug=topic.replace(" ", "-")))
        db_session.commit()

        token = verified["access_token"]
        for topic in topics:
            assert _lookup(client, token, topic).json()["exists"] is True

        # Newest first, and the first topic searched is gone.
        assert _recent_slugs(client, token) == ["air-quality", "birdsong", "chess-openings"]
        # Evicted from storage, not merely hidden by the query.
        assert db_session.query(BridgeRecentSearch).count() == 3

    def test_searching_again_bumps_instead_of_duplicating(self, client, verified, db_session):
        topics = ["wine quality", "chess openings", "birdsong"]
        for topic in topics:
            db_session.add(_verdict_row(topic_slug=topic.replace(" ", "-")))
        db_session.commit()

        token = verified["access_token"]
        for topic in topics:
            _lookup(client, token, topic)
        _lookup(client, token, "wine quality")

        assert _recent_slugs(client, token) == ["wine-quality", "birdsong", "chess-openings"]
        # A repeat is not a new search: nothing was evicted to make room for it.
        assert db_session.query(BridgeRecentSearch).count() == 3

    def test_scoped_to_one_step(self, client, verified, db_session):
        """A topic is assessed per step, so looking it up for step0 says nothing
        about step1 and must not appear there."""
        db_session.add(_verdict_row(topic_slug="wine-quality", model_id="step0"))
        db_session.add(_verdict_row(topic_slug="chess-openings", model_id="step1"))
        db_session.commit()
        token = verified["access_token"]
        _lookup(client, token, "wine quality", model_id="step0")
        _lookup(client, token, "chess openings", model_id="step1")

        assert _recent_slugs(client, token, model_id="step0") == ["wine-quality"]
        assert _recent_slugs(client, token, model_id="step1") == ["chess-openings"]

    def test_one_students_searches_are_their_own(self, client, outbox, verified, db_session):
        db_session.add(_verdict_row())
        db_session.commit()
        _lookup(client, verified["access_token"], TOPIC)

        other = register_and_verify(client, outbox, username="bob", email="bob@example.com")
        assert _recent_slugs(client, other["access_token"]) == []

    def test_a_negative_verdict_still_counts_as_a_search(self, client, verified, db_session):
        """"Nothing usable found" is an answer, and an expensive one. Hiding it
        invites the student to spend another run asking the same question."""
        row = _verdict_row(topic_slug="quidditch-scores")
        row.verdict = {"verdict": "not_at_hobby_scale", "summary": "nothing usable turned up"}
        db_session.add(row)
        db_session.commit()
        token = verified["access_token"]
        _lookup(client, token, "quidditch scores")

        entries = client.get("/bridge/recent", headers=auth_header(token)).json()
        assert [e["verdict_value"] for e in entries] == ["not_at_hobby_scale"]

    def test_a_search_with_no_verdict_behind_it_never_lists(
        self, client, verified, db_session, bridge_enabled
    ):
        """A queued run has not answered anything yet, and a failed one never
        will. Neither has a page to open, so neither takes a slot."""
        _post_run(client, verified["access_token"])  # queues, no verdict
        assert _recent_slugs(client, verified["access_token"]) == []

        job = db_session.query(BridgeJob).one()
        job.status = BridgeJobStatus.FAILED.value
        db_session.commit()
        assert _recent_slugs(client, verified["access_token"]) == []

    def test_a_row_whose_verdict_vanished_stops_listing(self, client, verified, db_session):
        """An INNER JOIN, so the row goes quiet rather than drawing a card that
        404s when the student clicks it."""
        db_session.add(_verdict_row())
        db_session.commit()
        token = verified["access_token"]
        _lookup(client, token, TOPIC)
        assert _recent_slugs(client, token) == ["premier-league-football-results"]

        db_session.query(BridgeVerdict).delete()
        db_session.commit()
        assert _recent_slugs(client, token) == []

    def test_a_run_that_hits_the_library_mid_flight_is_still_recorded(
        self, client, verified, db_session, bridge_enabled
    ):
        """The race backstop: a verdict landing between the lookup and the run
        (another tab, or someone else's run finishing) is still their search."""
        db_session.add(_verdict_row())
        db_session.commit()
        response = _post_run(client, verified["access_token"])
        assert response.json()["library_hit"] is True
        assert _recent_slugs(client, verified["access_token"]) == [
            "premier-league-football-results"
        ]
