"""
SMTP / console backends that append JSONL rows to logs/email_send.jsonl.
"""
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

from topteens.email_logging import log_from_email_message


class LoggingSMTPEmailBackend(SMTPEmailBackend):
    def _send(self, message):
        try:
            result = super()._send(message)
            log_from_email_message(message, 'sent' if result else 'not_sent', None)
            return result
        except Exception as exc:
            log_from_email_message(message, 'failed', str(exc))
            raise


class LoggingConsoleEmailBackend(ConsoleEmailBackend):
    def send_messages(self, email_messages):
        n = super().send_messages(email_messages)
        for message in email_messages:
            log_from_email_message(message, 'console', None)
        return n
