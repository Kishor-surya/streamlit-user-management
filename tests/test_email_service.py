from unittest.mock import MagicMock, patch

from email_service import SmtpConfig, build_welcome_email, send_email, send_welcome_email


def test_build_welcome_email_headers():
    msg = build_welcome_email("alice@example.com", "Alice", "Engineering", "Manager", "sender@example.com")
    assert msg["To"] == "alice@example.com"
    assert msg["From"] == "sender@example.com"
    assert "PeopleDesk" in msg["Subject"]


def test_build_welcome_email_body_contains_details():
    msg = build_welcome_email("alice@example.com", "Alice", "Engineering", "Manager", "sender@example.com")
    text_body = msg.get_body(preferencelist=("plain",)).get_content()
    html_body = msg.get_body(preferencelist=("html",)).get_content()

    assert "Alice" in text_body
    assert "Engineering" in text_body
    assert "Manager" in text_body
    assert "Alice" in html_body
    assert "Engineering" in html_body
    assert "Manager" in html_body


def test_send_email_uses_tls_and_login():
    config = SmtpConfig(sender_email="sender@example.com", sender_password="secret")
    msg = build_welcome_email("alice@example.com", "Alice", "Engineering", "Manager", config.sender_email)

    smtp_instance = MagicMock()
    smtp_instance.__enter__.return_value = smtp_instance
    with patch("email_service.smtplib.SMTP", return_value=smtp_instance) as smtp_cls:
        send_email(msg, config)

    smtp_cls.assert_called_once_with(config.host, config.port)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with(config.sender_email, config.sender_password)
    smtp_instance.send_message.assert_called_once_with(msg)


def test_send_email_skips_tls_when_disabled():
    config = SmtpConfig(sender_email="sender@example.com", sender_password="secret", use_tls=False)
    msg = build_welcome_email("alice@example.com", "Alice", "Engineering", "Manager", config.sender_email)

    smtp_instance = MagicMock()
    smtp_instance.__enter__.return_value = smtp_instance
    with patch("email_service.smtplib.SMTP", return_value=smtp_instance):
        send_email(msg, config)

    smtp_instance.starttls.assert_not_called()
    smtp_instance.send_message.assert_called_once_with(msg)


def test_send_welcome_email_builds_and_sends():
    config = SmtpConfig(sender_email="sender@example.com", sender_password="secret")

    with patch("email_service.send_email") as mock_send:
        send_welcome_email("alice@example.com", "Alice", "Engineering", "Manager", config)

    mock_send.assert_called_once()
    sent_msg, sent_config = mock_send.call_args[0]
    assert sent_msg["To"] == "alice@example.com"
    assert sent_config is config
