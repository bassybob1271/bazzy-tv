"""Outgoing email: sign-up verification and split-sheet invites.

Sends through any SMTP server. bazzy.tv mail is Google Workspace, so: SMTP_HOST=smtp.gmail.com,
SMTP_PORT=587, SMTP_USER=hello@bazzy.tv, SMTP_PASSWORD=<an app password for that mailbox>.
With no SMTP_HOST (local dev, tests) messages are logged instead and kept in OUTBOX.
"""
import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import settings

log = structlog.get_logger()
OUTBOX: list[EmailMessage] = []


def _send_now(msg: EmailMessage):
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
        s.starttls()
        if settings.SMTP_USER:
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.send_message(msg)


async def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    if not settings.SMTP_HOST:
        OUTBOX.append(msg)
        log.info("email.not_sent_no_smtp", to=to, subject=subject, body=text)
        return False
    try:
        await asyncio.to_thread(_send_now, msg)
        log.info("email.sent", to=to, subject=subject)
        return True
    except Exception as e:  # never fail the request because mail is down
        log.warning("email.failed", to=to, subject=subject, error=str(e))
        return False


def button_html(heading: str, body: str, cta: str, url: str) -> str:
    return f"""<div style="background:#0B0D14;padding:32px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#E8ECF7">
<div style="max-width:520px;margin:0 auto;background:#141826;border:1px solid #232a40;border-radius:14px;padding:28px">
<div style="font-weight:800;letter-spacing:.08em;font-size:13px;color:#4F8EF7">BAZZY TV</div>
<h1 style="font-size:22px;margin:14px 0 10px">{heading}</h1>
<p style="color:#A0A8C0;line-height:1.55;margin:0 0 22px">{body}</p>
<a href="{url}" style="display:inline-block;background:#4F8EF7;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:999px">{cta}</a>
<p style="color:#5A607A;font-size:12px;margin-top:22px">Bazzy TV · Brooklyn, NY · films, Bazzy Live and BazzyBox on one account</p>
</div></div>"""
