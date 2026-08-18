"""services/email_drain.py — claim, deliver, retry, and the resolve hop.

Patch targets differ and both are load-bearing:

* `_handle` calls the four senders through email_drain's OWN module namespace
  (they are imported by name at module scope), so those patch on
  `backend.services.email_drain`.
* `_resolve_forgot_password` imports `issue_password_reset` INSIDE the function
  body to avoid an import cycle, so that one would patch on
  `backend.core.verification` — here it is left alone and runs for real, which is
  what makes the two-hop reset flow testable.

`run()` is not exercised: it owns its own SessionLocal and sleeps in an unbounded
loop. Every decision it makes is in `drain_one`, which is called directly.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.core.config import settings
from backend.core.outbox import enqueue_email
from backend.models.EmailOutbox import EmailOutbox, EmailOutboxStatus, EmailType, utcnow
from backend.services import email_drain
from backend.services.email_drain import _claim, _fail, drain_one, reclaim_stale
from backend.tests.helpers import register_and_verify


@pytest.fixture()
def sent(monkeypatch):
    """Capture outbound sends instead of calling Resend."""
    captured: list[tuple[str, dict]] = []

    def stub(kind):
        def _send(**kwargs):
            captured.append((kind, kwargs))
        return _send

    for attr, kind in [
        ("send_verification_email", "verify_email"),
        ("send_password_reset_email", "password_reset"),
        ("send_account_exists_email", "account_exists"),
        ("send_email_changed_notification", "email_changed"),
    ]:
        monkeypatch.setattr(email_drain, attr, stub(kind))
    return captured


def _enqueue(db, email_type, payload) -> EmailOutbox:
    enqueue_email(db, email_type, payload)
    db.commit()
    return db.execute(select(EmailOutbox)).scalars().all()[-1]


def _rows(db) -> list[EmailOutbox]:
    db.expire_all()
    return db.execute(select(EmailOutbox).order_by(EmailOutbox.created_at)).scalars().all()


# --------------------------------------------------------------------------- #
# enqueue_email — the staging contract
# --------------------------------------------------------------------------- #

def test_enqueueing_stages_a_row_without_committing(db_session):
    """The caller owns the commit, so an email is only durable if the change that
    triggered it also committed. A rollback must leave no orphan send."""
    enqueue_email(db_session, EmailType.VERIFY_EMAIL, {"to_email": "a@b.com", "token": "t"})
    db_session.rollback()

    assert _rows(db_session) == []


def test_a_staged_row_starts_queued_with_no_attempts(db_session):
    row = _enqueue(db_session, EmailType.VERIFY_EMAIL, {"to_email": "a@b.com", "token": "t"})
    assert row.status == EmailOutboxStatus.QUEUED.value
    assert row.attempts == 0


# --------------------------------------------------------------------------- #
# drain_one — the happy paths
# --------------------------------------------------------------------------- #

def test_draining_an_empty_queue_reports_no_work(db_session, sent):
    assert drain_one(db_session) is False
    assert sent == []


@pytest.mark.parametrize(
    "email_type,payload,expected_kind",
    [
        (EmailType.VERIFY_EMAIL, {"to_email": "a@b.com", "token": "t"}, "verify_email"),
        (EmailType.PASSWORD_RESET, {"to_email": "a@b.com", "token": "t"}, "password_reset"),
        (EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"}, "account_exists"),
        (EmailType.EMAIL_CHANGED, {"to_email": "a@b.com", "new_email": "c@d.com"}, "email_changed"),
    ],
)
def test_each_send_type_reaches_its_own_sender(db_session, sent, email_type, payload, expected_kind):
    _enqueue(db_session, email_type, payload)

    assert drain_one(db_session) is True

    assert [kind for kind, _ in sent] == [expected_kind]
    assert sent[0][1]["to_email"] == "a@b.com"


def test_a_delivered_row_is_deleted_rather_than_marked_sent(db_session, sent):
    """The table is a queue, not a log: successful rows leave. That is why
    assertions about what was *sent* have to look at the sender, not the table."""
    _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})

    drain_one(db_session)

    assert _rows(db_session) == []


def test_rows_are_drained_oldest_first(db_session, sent):
    _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "first@b.com"})
    second = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "second@b.com"})
    second.created_at = second.created_at + timedelta(seconds=5)
    db_session.commit()

    drain_one(db_session)

    assert sent[0][1]["to_email"] == "first@b.com"


def test_an_unknown_email_type_fails_the_row_rather_than_crashing_the_drainer(db_session, sent):
    _enqueue(db_session, EmailType.VERIFY_EMAIL, {"to_email": "a@b.com", "token": "t"})
    db_session.execute(EmailOutbox.__table__.update().values(email_type="not_a_type"))
    db_session.commit()

    assert drain_one(db_session) is True  # handled, not raised

    row = _rows(db_session)[0]
    assert row.status == EmailOutboxStatus.QUEUED.value  # requeued for retry
    assert "unknown email_type" in row.error


# --------------------------------------------------------------------------- #
# The resolve hop — enumeration resistance in action
# --------------------------------------------------------------------------- #

def test_a_forgot_password_request_for_a_real_user_becomes_a_reset_send(client, outbox, db_session, sent):
    """Two hops by design: the endpoint does no user lookup at all, so response
    timing can't reveal whether the address is registered. The drain is where the
    lookup, the cooldown and the token minting happen."""
    register_and_verify(client, outbox, email="alice@example.com")
    db_session.execute(EmailOutbox.__table__.delete())
    db_session.commit()

    _enqueue(db_session, EmailType.FORGOT_PASSWORD_REQUEST, {"email": "alice@example.com"})

    assert drain_one(db_session) is True          # resolves -> stages the send row
    queued = _rows(db_session)
    assert [r.email_type for r in queued] == [EmailType.PASSWORD_RESET.value]
    assert queued[0].payload["token"]

    assert drain_one(db_session) is True          # delivers it
    assert [kind for kind, _ in sent] == ["password_reset"]


def test_a_forgot_password_request_for_an_unknown_address_resolves_to_nothing(db_session, sent):
    _enqueue(db_session, EmailType.FORGOT_PASSWORD_REQUEST, {"email": "ghost@example.com"})

    assert drain_one(db_session) is True

    # The resolve row is consumed either way — identical work, identical timing.
    assert _rows(db_session) == []
    assert sent == []


# --------------------------------------------------------------------------- #
# Retry, backoff and the dead letter
# --------------------------------------------------------------------------- #

def test_a_failing_send_is_requeued_with_a_future_next_attempt(db_session, monkeypatch, sent):
    def boom(**kwargs):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(email_drain, "send_account_exists_email", boom)
    _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})

    assert drain_one(db_session) is True

    row = _rows(db_session)[0]
    assert row.status == EmailOutboxStatus.QUEUED.value
    assert row.attempts == 1
    assert row.error == "resend is down"
    assert row.next_attempt_at > utcnow()


def test_a_row_backing_off_is_not_claimed_before_it_is_due(db_session, sent):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.next_attempt_at = utcnow() + timedelta(hours=1)
    db_session.commit()

    assert _claim(db_session) is None
    assert drain_one(db_session) is False


def test_a_row_becomes_claimable_once_its_backoff_has_elapsed(db_session, sent):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.next_attempt_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert drain_one(db_session) is True
    assert [kind for kind, _ in sent] == ["account_exists"]


def test_a_row_that_exhausts_its_attempts_is_marked_dead(db_session):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.attempts = settings.EMAIL_OUTBOX_MAX_ATTEMPTS
    db_session.commit()

    _fail(db_session, row.id, RuntimeError("permanent failure"))

    dead = _rows(db_session)[0]
    assert dead.status == EmailOutboxStatus.DEAD.value


def test_a_dead_row_has_its_token_scrubbed_from_the_payload(db_session):
    """A dead row sticks around for inspection, so it must not keep a live
    password-reset token sitting in the table indefinitely."""
    row = _enqueue(
        db_session, EmailType.PASSWORD_RESET, {"to_email": "a@b.com", "token": "secret-token"}
    )
    row.attempts = settings.EMAIL_OUTBOX_MAX_ATTEMPTS
    db_session.commit()

    _fail(db_session, row.id, RuntimeError("gave up"))

    dead = _rows(db_session)[0]
    assert dead.status == EmailOutboxStatus.DEAD.value
    assert "token" not in dead.payload
    assert dead.payload["to_email"] == "a@b.com"  # the rest is kept for debugging


def test_a_dead_row_is_never_claimed_again(db_session, sent):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.status = EmailOutboxStatus.DEAD.value
    db_session.commit()

    assert drain_one(db_session) is False


def test_a_failed_resolve_leaves_no_half_written_token(db_session, monkeypatch, client, outbox):
    """drain_one rolls back before recording the failure, so a resolve that
    blew up after staging a token doesn't leave that token behind."""
    from backend.models.EmailToken import EmailToken

    register_and_verify(client, outbox, email="alice@example.com")
    db_session.execute(EmailOutbox.__table__.delete())
    db_session.execute(EmailToken.__table__.delete())
    db_session.commit()

    def stage_then_fail(db, email):
        from backend.core.verification import issue_password_reset
        user = db.execute(
            select(email_drain.User).where(email_drain.User.email == email)
        ).scalars().first()
        issue_password_reset(user, db)
        raise RuntimeError("died after staging")

    monkeypatch.setattr(email_drain, "_resolve_forgot_password", stage_then_fail)
    _enqueue(db_session, EmailType.FORGOT_PASSWORD_REQUEST, {"email": "alice@example.com"})

    assert drain_one(db_session) is True

    db_session.expire_all()
    assert db_session.execute(select(EmailToken)).scalars().all() == []
    assert _rows(db_session)[0].status == EmailOutboxStatus.QUEUED.value


# --------------------------------------------------------------------------- #
# reclaim_stale
# --------------------------------------------------------------------------- #

def test_a_row_stuck_sending_past_the_cutoff_is_requeued(db_session):
    """A drainer that dies mid-send leaves a row `sending` forever; without the
    sweep that email is never delivered and never retried."""
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.status = EmailOutboxStatus.SENDING.value
    row.claimed_at = utcnow() - timedelta(seconds=settings.EMAIL_OUTBOX_CLAIM_STALE_SECONDS + 60)
    db_session.commit()

    assert reclaim_stale(db_session) == 1
    assert _rows(db_session)[0].status == EmailOutboxStatus.QUEUED.value


def test_a_row_recently_claimed_is_left_alone(db_session):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.status = EmailOutboxStatus.SENDING.value
    row.claimed_at = utcnow()
    db_session.commit()

    assert reclaim_stale(db_session) == 0
    assert _rows(db_session)[0].status == EmailOutboxStatus.SENDING.value


def test_reclaiming_is_idempotent_so_several_drainers_can_run_it(db_session):
    row = _enqueue(db_session, EmailType.ACCOUNT_EXISTS, {"to_email": "a@b.com"})
    row.status = EmailOutboxStatus.SENDING.value
    row.claimed_at = utcnow() - timedelta(seconds=settings.EMAIL_OUTBOX_CLAIM_STALE_SECONDS + 60)
    db_session.commit()

    assert reclaim_stale(db_session) == 1
    assert reclaim_stale(db_session) == 0
