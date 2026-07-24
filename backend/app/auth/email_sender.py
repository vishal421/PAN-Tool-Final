"""
Sends verification-code and password-reset-code emails via Brevo.

Delivery path, in order of preference:
  1. Brevo transactional email HTTP API (BREVO_API_KEY set).
  2. Brevo SMTP relay (BREVO_SMTP_HOST/USERNAME/PASSWORD set).
  3. Neither configured: log a warning (never the code itself - see the
     module docstring in app/auth/otp.py) and return, same "honest
     fallback" philosophy as the app's original SMTP sender.

Never include the OTP in logs or exceptions raised from here - only the
caller (app/auth/otp.py) ever holds the raw code, and it's discarded once
this function returns.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import requests

from app.core.config import settings

logger = logging.getLogger("app.auth.email")

_BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _otp_email_html(*, heading: str, intro: str, code: str, expire_minutes: int) -> str:
    return f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
            <tr>
              <td style="background:#111827;padding:20px 32px;">
                <span style="color:#ffffff;font-size:18px;font-weight:700;">{settings.mail_from_name}</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h2 style="margin:0 0 12px;color:#111827;font-size:20px;">{heading}</h2>
                <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.5;">{intro}</p>
                <div style="text-align:center;margin:0 0 24px;">
                  <span style="display:inline-block;background:#f4f5f7;border-radius:6px;padding:16px 28px;
                               font-size:32px;font-weight:700;letter-spacing:8px;color:#111827;">{code}</span>
                </div>
                <p style="margin:0 0 8px;color:#6b7280;font-size:13px;">
                  This code expires in {expire_minutes} minutes.
                </p>
                <p style="margin:0;color:#b91c1c;font-size:13px;font-weight:600;">
                  Do not share this code with anyone.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;background:#f9fafb;color:#9ca3af;font-size:12px;">
                If you didn't request this, you can safely ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _plain_text(intro: str, code: str, expire_minutes: int) -> str:
    return (
        f"{intro}\n\n"
        f"Your code: {code}\n\n"
        f"This code expires in {expire_minutes} minutes.\n"
        "Do not share this code with anyone.\n\n"
        "If you didn't request this, you can safely ignore this email."
    )


def _send_via_brevo_api(to_email: str, subject: str, html: str, text: str) -> None:
    resp = requests.post(
        _BREVO_API_URL,
        headers={"api-key": settings.brevo_api_key, "Content-Type": "application/json", "accept": "application/json"},
        json={
            "sender": {"name": settings.mail_from_name, "email": settings.mail_from_address},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html,
            "textContent": text,
        },
        timeout=10,
    )
    resp.raise_for_status()


def _send_via_brevo_smtp(to_email: str, subject: str, html: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.mail_from_name} <{settings.mail_from_address}>"
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.brevo_smtp_host, settings.brevo_smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.brevo_smtp_username and settings.brevo_smtp_password:
            smtp.login(settings.brevo_smtp_username, settings.brevo_smtp_password)
        smtp.send_message(msg)


def _send(to_email: str, subject: str, html: str, text: str) -> None:
    try:
        if settings.brevo_api_key:
            _send_via_brevo_api(to_email, subject, html, text)
        elif settings.brevo_smtp_host:
            _send_via_brevo_smtp(to_email, subject, html, text)
        else:
            logger.warning(
                "Brevo is not configured (set BREVO_API_KEY or BREVO_SMTP_HOST/USERNAME/PASSWORD) - "
                "skipping email send to %s. Mail service unavailable.",
                to_email,
            )
    except Exception:
        # Don't 500 the request or leak provider details to the client for a
        # transient mail-provider failure; the caller returns a generic
        # response regardless. Loud server-side log for the operator to
        # notice - deliberately without the OTP itself.
        logger.exception("Failed to send email to %s via Brevo", to_email)


def send_verification_email(to_email: str, code: str) -> None:
    subject = f"Verify your email - {settings.mail_from_name}"
    intro = "Use the code below to verify your email address and activate your account."
    html = _otp_email_html(
        heading="Verify your email address",
        intro=intro,
        code=code,
        expire_minutes=settings.otp_expire_minutes,
    )
    text = _plain_text(intro, code, settings.otp_expire_minutes)
    _send(to_email, subject, html, text)


def send_password_reset_otp_email(to_email: str, code: str) -> None:
    subject = f"Reset your password - {settings.mail_from_name}"
    intro = "We received a request to reset your password. Use the code below to continue."
    html = _otp_email_html(
        heading="Reset your password",
        intro=intro,
        code=code,
        expire_minutes=settings.otp_expire_minutes,
    )
    text = _plain_text(intro, code, settings.otp_expire_minutes)
    _send(to_email, subject, html, text)
