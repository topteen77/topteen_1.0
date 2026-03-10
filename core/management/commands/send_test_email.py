"""
Send a test email to verify SMTP and deliverability (inbox vs spam).
Usage:
  python manage.py send_test_email your@email.com
  python manage.py send_test_email your@email.com --invoice-style
"""
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class Command(BaseCommand):
    help = 'Send a test email to the given address to verify SMTP and check inbox/spam delivery.'

    def add_arguments(self, parser):
        parser.add_argument(
            'to_email',
            type=str,
            help='Email address to send the test message to',
        )
        parser.add_argument(
            '--invoice-style',
            action='store_true',
            help='Send a second email that looks like an invoice (subject/body) to test payment email format.',
        )

    def handle(self, *args, **options):
        to_email = options['to_email'].strip()
        if not to_email or '@' not in to_email:
            self.stderr.write(self.style.ERROR('Provide a valid email address.'))
            return

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'TOPTEEN_FROM_EMAIL', 'noreply@example.com')
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        self.stdout.write(f'From: {from_email}')
        self.stdout.write(f'Backend: {backend}')
        self.stdout.write(f'To: {to_email}')

        # 1) Plain test email
        subject = '[TopTeen] Test email – deliverability check'
        text_body = (
            'This is a test email from TopTeen.\n\n'
            'If you receive this in your inbox, SMTP is working. '
            'If it lands in spam, check SPF/DKIM/DMARC for your sending domain and use a consistent From address.'
        )
        html_body = (
            '<p>This is a test email from <strong>TopTeen</strong>.</p>'
            '<p>If you receive this in your <strong>inbox</strong>, SMTP is working.</p>'
            '<p>If it lands in <strong>spam</strong>, check SPF/DKIM/DMARC for your sending domain.</p>'
        )
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[to_email],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)
            self.stdout.write(self.style.SUCCESS('Test email sent successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to send test email: {e}'))
            return

        # 2) Optional invoice-style email (same format as payment/invoice emails)
        if options.get('invoice_style'):
            subject2 = 'Invoice INV-TEST - Stream Sorter'
            text_body2 = (
                'Please find your invoice attached.\n\n'
                'Transaction ID: pay-test-123\nAmount: ₹ 499\n\nThank you.'
            )
            try:
                msg2 = EmailMultiAlternatives(
                    subject=subject2,
                    body=text_body2,
                    from_email=from_email,
                    to=[to_email],
                )
                msg2.attach_alternative(f'<p>{text_body2.replace(chr(10), "<br>")}</p>', 'text/html')
                msg2.send(fail_silently=False)
                self.stdout.write(self.style.SUCCESS('Invoice-style test email sent successfully.'))
            except Exception as e:
                self.stderr.write(self.style.WARNING(f'Invoice-style email failed: {e}'))

        self.stdout.write('')
        self.stdout.write('Check the recipient inbox (and spam folder). For better inbox delivery:')
        self.stdout.write('  - Verify the From address domain in AWS SES (or your SMTP provider).')
        self.stdout.write('  - Set SPF, DKIM, and DMARC DNS records for the sending domain.')
        self.stdout.write('  - Use a consistent From address (e.g. noreply@yourdomain.com).')
