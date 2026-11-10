"""Send digests and test email to the recipients configured by the NAS operator."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger("uvicorn.error")


def email_available():
    return all(os.environ.get(key, "").strip() for key in ("CTI_SMTP_HOST", "CTI_SMTP_FROM", "CTI_SMTP_TO"))


def _send_email(subject, body):
    host = os.environ["CTI_SMTP_HOST"].strip()
    security = os.environ.get("CTI_SMTP_SECURITY", "ssl").strip().lower()
    if security not in {"ssl", "starttls"}:
        raise ValueError("Invalid SMTP security mode")
    port = int(os.environ.get("CTI_SMTP_PORT", "").strip() or (465 if security == "ssl" else 587))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid SMTP port")
    username = os.environ.get("CTI_SMTP_USERNAME", "")
    password = os.environ.get("CTI_SMTP_PASSWORD", "")

    message = EmailMessage()
    message["From"] = os.environ["CTI_SMTP_FROM"]
    message["To"] = os.environ["CTI_SMTP_TO"]
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    connection = (smtplib.SMTP_SSL(host, port, timeout=15, context=context) if security == "ssl"
                  else smtplib.SMTP(host, port, timeout=15))
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        if username:
            smtp.login(username, password)
        return smtp.send_message(message)


def send_test_email():
    refused = _send_email("Cyber Intel: test email", "This is a test email from Cyber Intel Threat Observatory.")
    return len(refused)


def send_digest(counts, findings):
    if not email_available() or not (counts["new"] or counts["updated"]):
        return

    try:
        subject = f"Cyber Intel: {counts['new']} new, {counts['updated']} updated"
        lines = [f"The latest refresh collected {counts['new']} new findings and {counts['updated']} material updates.", ""]
        for item, result in findings:
            lines.append(f"{result.title()} | {item['severity']} | {item['title']}")
            if item.get("url"):
                lines.append(item["url"])
            lines.append("")
        if counts["new"] + counts["updated"] > len(findings):
            lines.append("Open the dashboard for the complete list.")
        _send_email(subject, "\n".join(lines))
        logger.info("Cyber Intel email digest sent")
    except (OSError, ValueError) as error:
        logger.warning("Cyber Intel email digest failed (%s)", type(error).__name__)
