import os
import ssl
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Dict, List, Tuple

from dotenv import load_dotenv


@dataclass
class SMTPSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    sender_name: str | None = None


def load_smtp_settings_from_env() -> SMTPSettings:
    load_dotenv()  # loads .env into process env; no-op if already loaded

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "465"))  # default SMTPS
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", "")
    sender_name = os.getenv("SMTP_FROM_NAME", "") or None

    missing = [k for k, v in [
        ("SMTP_HOST", host), ("SMTP_USERNAME", username),
        ("SMTP_PASSWORD", password), ("SMTP_FROM", sender)
    ] if not v]
    if missing:
        raise RuntimeError(f"Ontbrekende .env variabelen: {', '.join(missing)}")

    return SMTPSettings(
        host=host, port=port, username=username, password=password,
        sender=sender, sender_name=sender_name
    )


def _format_sender(settings: SMTPSettings) -> str:
    return f"{settings.sender_name} <{settings.sender}>" if settings.sender_name else settings.sender


def send_secret_santa_emails(
    assignment: Dict[str, str],
    emails: Dict[str, str],
    settings: SMTPSettings,
    dry_run: bool = False
) -> List[Tuple[str, str]]:
    """
    Sends one email per giver that has an email present.
    Skips givers without an email silently (new behavior).
    Returns a list of (giver, recipient_email) actually sent/attempted.
    """
    attempted: List[Tuple[str, str]] = []
    messages: List[EmailMessage] = []
    for giver, receiver in assignment.items():
        to_addr = emails.get(giver)
        if not to_addr:
            continue  # skip silently
        msg = EmailMessage()
        msg["Subject"] = "Secret Santa"
        msg["From"] = _format_sender(settings)
        msg["To"] = to_addr
        body = (
            f"Hey {giver.capitalize()},\n\n"
            f"De kerstman heeft me verteld dat jij dit jaar voor {receiver.capitalize()} iets leuks mag uitkiezen!\n\n"
            "Wees origineel en mondje toe hé! 😉\n\n"
            "Groetjes,\n"
            "De Super Secret Santa Elfen Commissie"
        )
        msg.set_content(body)
        messages.append(msg)
        attempted.append((giver, to_addr))
    if dry_run:
        return attempted
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.host, settings.port, context=context) as server:
        server.login(settings.username, settings.password)
        for msg in messages:
            server.send_message(msg)
    return attempted
