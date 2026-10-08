"""Outbound mail for auth tokens (v0.5 P-1).

Default ``log`` delivery prints the link (dev / invite preview).
Optional SMTP when ``MAIL_BACKEND=smtp``.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger("civsim.mailer")


def public_app_url() -> str:
    s = get_settings()
    return (getattr(s, "public_app_url", None) or "http://localhost:3000").rstrip("/")


def deliver_auth_link(
    *,
    to_email: str,
    purpose: str,
    raw_token: str,
    username: str,
) -> dict:
    """Send or log an auth link. Always returns a delivery receipt for tests/dev."""
    s = get_settings()
    base = public_app_url()
    if purpose == "reset":
        path = f"/login?mode=reset&token={raw_token}"
        subject = "CivilSimulator 密码重置"
        blurb = "点击链接重置密码（1 小时内有效）："
    elif purpose == "magic":
        path = f"/login?mode=magic&token={raw_token}"
        subject = "CivilSimulator 登录链接"
        blurb = "点击魔法链接登录（15 分钟内有效）："
    elif purpose == "verify":
        path = f"/login?mode=verify&token={raw_token}"
        subject = "CivilSimulator 验证邮箱"
        blurb = "点击链接验证邮箱（24 小时内有效）："
    else:
        raise ValueError(f"unknown purpose: {purpose}")

    link = f"{base}{path}"
    body = f"你好 {username}，\n\n{blurb}\n{link}\n\n若非本人操作可忽略。\n"
    backend = (getattr(s, "mail_backend", "log") or "log").strip().lower()
    receipt: dict = {
        "backend": backend,
        "to": to_email,
        "purpose": purpose,
        "link": link,
    }

    if backend == "smtp":
        host = (getattr(s, "smtp_host", None) or "").strip()
        if not host:
            raise RuntimeError("MAIL_BACKEND=smtp 但未配置 SMTP_HOST")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = getattr(s, "mail_from", None) or "noreply@localhost"
        msg["To"] = to_email
        msg.set_content(body)
        port = int(getattr(s, "smtp_port", 587) or 587)
        user = getattr(s, "smtp_user", None) or ""
        password = getattr(s, "smtp_password", None) or ""
        use_tls = bool(getattr(s, "smtp_tls", True))
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        log.info("smtp mail sent purpose=%s to=%s", purpose, to_email)
        return receipt

    # Default: log delivery (safe for local / invite preview).
    log.warning(
        "AUTH_MAIL purpose=%s to=%s user=%s link=%s",
        purpose,
        to_email,
        username,
        link,
    )
    receipt["logged"] = True
    return receipt
