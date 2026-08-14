"""
SMTP / console backends that append JSONL rows to logs/email_send.jsonl.
"""
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

from topteens.email_logging import log_from_email_message


def _logged_by_comservice(message) -> bool:
    """ComService.send_mail writes the Email logs row itself; skip duplicate backend rows."""
    return bool(getattr(message, "_topteen_logged_by_comservice", False))


class LoggingSMTPEmailBackend(SMTPEmailBackend):
    def _send(self, message):
        try:
            result = super()._send(message)
            if not _logged_by_comservice(message):
                log_from_email_message(message, 'sent' if result else 'not_sent', None)
            return result
        except Exception as exc:
            if not _logged_by_comservice(message):
                log_from_email_message(message, 'failed', str(exc))
            raise


class LoggingConsoleEmailBackend(ConsoleEmailBackend):
    def send_messages(self, email_messages):
        n = super().send_messages(email_messages)
        for message in email_messages:
            if _logged_by_comservice(message):
                continue
            log_from_email_message(message, 'console', None)
        return n
