"""
Corporate-email-only registration: blocks signups from free consumer email
providers and known disposable/temporary-inbox services.

Design note: this is a domain blocklist, not a domain allowlist. An
allowlist ("only these corporate domains may sign up") isn't workable here
since we have no fixed list of legitimate companies - anyone's real work
email should be accepted. A blocklist of known-personal and known-disposable
providers is the standard way to approximate "corporate email only" without
that constraint.

To add more blocked domains later without a code change, set
EXTRA_BLOCKED_EMAIL_DOMAINS in the environment (comma-separated) - see
app/core/config.py. To add them permanently, add to the sets below.
"""

from __future__ import annotations

from app.core.config import settings

# Free/consumer webmail providers.
BLOCKED_FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "ymail.com", "rocketmail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com",
    "zoho.com",
    "gmx.com",
    "mail.com",
    "proton.me", "protonmail.com",
    "tutanota.com", "tuta.io",
    "rediffmail.com",
    "yandex.com", "yandex.ru",
    "qq.com", "163.com", "126.com",
    "naver.com",
    "daum.net",
})

# Temporary / disposable inbox services.
BLOCKED_DISPOSABLE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com", "temp-mail.org",
    "10minutemail.com",
    "throwawaymail.com",
    "fakeinbox.com",
    "sharklasers.com",
    "getnada.com",
    "dispostable.com",
    "emailondeck.com",
    "maildrop.cc",
    "moakt.com",
})


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower()


def blocked_reason(email: str) -> str | None:
    """
    Returns a user-facing reason string if `email`'s domain is not allowed
    for registration, or None if it's fine (i.e. looks like a corporate
    address). Checked in this order so the message matches the actual
    category of the domain.
    """
    domain = _domain_of(email)
    if not domain:
        return "Please enter a valid email address."
    if domain in BLOCKED_DISPOSABLE_EMAIL_DOMAINS or domain in settings.extra_blocked_email_domains:
        return "Temporary/disposable email addresses are not allowed. Please use your corporate email address."
    if domain in BLOCKED_FREE_EMAIL_DOMAINS:
        return "Personal email addresses are not allowed. Please sign up with your corporate/business email address."
    return None


def is_corporate_email(email: str) -> bool:
    return blocked_reason(email) is None
