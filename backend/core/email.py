import resend

from backend.core.config import settings

# These senders are called only by the outbox drainer (backend.services.
# email_drain), never on the request path. They let Resend failures PROPAGATE so
# the drainer can catch them and schedule a retry — swallowing here would turn a
# transient Resend outage into a silently dropped email, the exact durability
# hole the outbox exists to close. The raw token is trusted as-is; it was minted
# and persisted by the caller, so this layer does no decoding/validation.


def send_verification_email(token: str, to_email: str) -> None:
    """Send the verification link."""
    resend.api_key = settings.RESEND_API_KEY
    # Link lands on the SPA, which POSTs the token to /auth/verify. Keeping it a
    # POST (not a GET on the API) means email scanners/link-preview bots that
    # pre-fetch the URL can't silently consume the single-use token.
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": "Verify your email for NC++",
        "html": (
            "<p>Click the link below to verify your email address.</p>"
            f'<a href="{verify_url}">Verify Email</a>'
            f"<p>This link expires in {settings.VERIFICATION_TTL_HOURS} hours.</p>"
        ),
    }

    resend.Emails.send(params)


def send_account_exists_email(to_email: str) -> None:
    """Sent when someone tries to register an email that already has an account.

    /auth/register returns the same generic response whether or not the address
    is taken (no enumeration), so this email is how the *real* owner is told what
    happened — the attacker probing the API never sees the victim's inbox."""
    resend.api_key = settings.RESEND_API_KEY
    login_url = f"{settings.FRONTEND_URL}/login"
    forgot_url = f"{settings.FRONTEND_URL}/forgot-password"

    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": "You already have an NC++ account",
        "html": (
            "<p>Someone (possibly you) just tried to sign up for NC++ with this "
            "email address, but an account already exists.</p>"
            f'<p><a href="{login_url}">Log in</a> or '
            f'<a href="{forgot_url}">reset your password</a> if you\'ve forgotten it.</p>'
            "<p>If this wasn't you, no account was created or changed — you can "
            "safely ignore this email.</p>"
        ),
    }

    resend.Emails.send(params)


def send_email_changed_notification(to_email: str, new_email: str) -> None:
    """Notify the PREVIOUS address that the account's email was changed.

    This is the real protection for an email change (we deliberately do NOT
    revoke sessions — the change already re-authenticates with the current
    password and re-verifies the new address). If the change was unauthorised,
    this is the only message that reaches the legitimate owner, so it points them
    at password reset — which DOES revoke every session — to lock an attacker out.
    """
    resend.api_key = settings.RESEND_API_KEY
    reset_url = f"{settings.FRONTEND_URL}/forgot-password"

    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": "Your NC++ email address was changed",
        "html": (
            f"<p>The email address on your NC++ account was just changed to "
            f"<strong>{new_email}</strong>.</p>"
            "<p>If you made this change, no action is needed.</p>"
            "<p><strong>If you did NOT</strong>, your account may be compromised. "
            f'Reset your password now to secure it: <a href="{reset_url}">Reset password</a> '
            "— this signs out every device.</p>"
        ),
    }

    resend.Emails.send(params)


def send_password_reset_email(token: str, to_email: str) -> None:
    """Send the password-reset link.

    Note the URL differs from verification: it lands on the SPA's reset page, not
    /verify-email. Reusing send_verification_email here was the bug — that link
    POSTs to /auth/verify, which rejects any token whose purpose != VERIFY_EMAIL,
    so a reset link built that way could never be consumed."""
    resend.api_key = settings.RESEND_API_KEY
    reset_url = f"{settings.FRONTEND_URL}/password-reset?token={token}"

    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": "Reset your password for NC++",
        "html": (
            "<p>We received a request to reset your password. "
            "Click the link below to choose a new one.</p>"
            f'<a href="{reset_url}">Reset Password</a>'
            f"<p>This link expires in {settings.RESET_TTL_HOURS} hours.</p>"
            "<p>If you didn't request this, you can safely ignore this email.</p>"
        ),
    }

    resend.Emails.send(params)
