"""Sends onboarding notification emails via SMTP (defaults tuned for Gmail).

Kept separate from app.py / utils.py so message construction can be unit
tested without touching the network, and the actual send can be tested with
a mocked SMTP client.
"""

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass
class SmtpConfig:
    sender_email: str
    sender_password: str
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True


def build_welcome_email(to_email: str, full_name: str, department: str, role: str, sender_email: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "You've been added to PeopleDesk"
    msg["From"] = sender_email
    msg["To"] = to_email

    msg.set_content(
        f"Hi {full_name},\n\n"
        "You have been added to PeopleDesk (User Management) with the following details:\n\n"
        f"Department: {department}\n"
        f"Role: {role}\n\n"
        "If you believe this was a mistake, please contact your administrator.\n\n"
        "Regards,\nPeopleDesk Team"
    )
    msg.add_alternative(
        f"""\
<html>
  <body style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; color:#1f2328;">
    <h2>Welcome, {full_name}! &#128075;</h2>
    <p>You have been added to <strong>PeopleDesk</strong> with the following details:</p>
    <table style="border-collapse: collapse;">
      <tr><td style="padding:4px 12px 4px 0;"><strong>Department</strong></td><td>{department}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;"><strong>Role</strong></td><td>{role}</td></tr>
    </table>
    <p>If you believe this was a mistake, please contact your administrator.</p>
    <p style="color:#6b7280; font-size: 0.85em;">This is an automated message from PeopleDesk.</p>
  </body>
</html>
""",
        subtype="html",
    )
    return msg


def send_email(msg: EmailMessage, config: SmtpConfig) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP(config.host, config.port) as server:
        if config.use_tls:
            server.starttls(context=context)
        server.login(config.sender_email, config.sender_password)
        server.send_message(msg)


def send_welcome_email(to_email: str, full_name: str, department: str, role: str, config: SmtpConfig) -> None:
    msg = build_welcome_email(to_email, full_name, department, role, config.sender_email)
    send_email(msg, config)
