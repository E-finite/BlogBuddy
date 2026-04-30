"""Helpers for sending transactional mail."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from src import config

logger = logging.getLogger(__name__)


def build_reset_password_url(token: str, request_base_url: str | None = None) -> str:
    """Build an absolute reset-password URL.

    Uses APP_PUBLIC_URL (env) when set, falls back to the request base URL.
    """
    base_url = config.APP_PUBLIC_URL or (
        request_base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError(
            "APP_PUBLIC_URL of request base URL is vereist voor reset-links. "
            "Stel APP_PUBLIC_URL in als environment variabele, bijv. https://blogbuddy.cloud"
        )
    return f"{base_url}/reset-password/{token}"


def send_password_reset_email(recipient_email: str, reset_url: str) -> tuple[bool, str]:
    """Send a password reset email through SMTP."""
    if not config.MAIL_SERVER or not config.MAIL_DEFAULT_SENDER:
        return False, "Mailconfig ontbreekt. Stel MAIL_SERVER en MAIL_DEFAULT_SENDER in."

    message = EmailMessage()
    message["Subject"] = "Wachtwoord resetten - Blog Generator"
    message["From"] = config.MAIL_DEFAULT_SENDER
    message["To"] = recipient_email
    message.set_content(
        "Je hebt een verzoek gedaan om je wachtwoord te resetten.\n\n"
        f"Open deze link om een nieuw wachtwoord in te stellen:\n{reset_url}\n\n"
        "Deze link is 1 uur geldig. Heb je dit niet aangevraagd, dan kun je deze e-mail negeren."
    )

    try:
        if config.MAIL_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.MAIL_SERVER, config.MAIL_PORT, context=context, timeout=15) as smtp:
                if config.MAIL_USERNAME:
                    smtp.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT, timeout=15) as smtp:
                if config.MAIL_USE_TLS:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                if config.MAIL_USERNAME:
                    smtp.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
                smtp.send_message(message)
    except smtplib.SMTPAuthenticationError:
        logger.exception(
            "SMTP authenticatie mislukt tijdens password reset mail")
        return False, "Mailserver authenticatie mislukt. Controleer MAIL_USERNAME en MAIL_PASSWORD."
    except TimeoutError:
        logger.warning(
            "SMTP timeout naar %s:%s tijdens password reset mail",
            config.MAIL_SERVER,
            config.MAIL_PORT,
        )
        return False, (
            f"Resetmail versturen timed out naar {config.MAIL_SERVER}:{config.MAIL_PORT}. "
            "Controleer firewall/netwerk of gebruik een mailprovider via HTTPS API."
        )
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Versturen van password reset mail mislukt")
        return False, f"Resetmail versturen mislukt: {exc}"

    return True, ""
