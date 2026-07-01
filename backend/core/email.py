import logging

import resend

from backend.core.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(token: str, to_email: str) -> None:
    """Send the verification link. Runs inside a BackgroundTask, so there's no
    client to surface failures to — log and move on. The user can re-trigger via
    /auth/resend-verification. The raw token is trusted as-is here; it was minted
    and persisted by the caller, so this layer does no decoding/validation."""
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

    try:
        resend.Emails.send(params)
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)


def send_password_reset_email(token: str, to_email: str) -> None:
    """Send the password-reset link. Like send_verification_email, this runs off
    the request path (inside forgot_password's BackgroundTask) so there's no
    client to surface failures to — log and move on.

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

    try:
        resend.Emails.send(params)
    except Exception:
        logger.exception("Failed to send password reset email to %s", to_email)
