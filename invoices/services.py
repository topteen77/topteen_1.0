"""
Invoice creation and PDF/email generation. No invoice for failed payments.
No invoice for institute-registered free students.
"""
from decimal import Decimal
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.core.files.base import ContentFile
from core import choices
from .models import Invoice, InvoiceConfiguration, InvoiceEmailLog
from communication.models import CommunicationLog


def is_institute_free_student_payment(payment):
    """True if this payment is for an institute-registered free student (no invoice should be generated/sent)."""
    from institute.models import StudentManagement
    if not getattr(payment, 'user_id', None):
        return False
    if getattr(payment, 'obj_type', None) == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
        if StudentManagement.objects.filter(student_id=payment.user_id).exists():
            return True
    if getattr(payment, 'gateway_receipt', None) and str(payment.gateway_receipt or '').startswith('Student_Psychometric'):
        return True
    return False


def get_config():
    """Get or create singleton InvoiceConfiguration."""
    config = InvoiceConfiguration.objects.filter(object_status=choices.ObjectStatus.ACTIVE).first()
    if not config:
        config = InvoiceConfiguration.objects.create()
    return config


def create_invoice_for_payment(payment):
    """Create Invoice for a successful payment and generate PDF + send emails. Idempotent. Institute free students only if config allows."""
    config = get_config()
    if is_institute_free_student_payment(payment) and not config.generate_invoice_for_institute_students:
        return None
    if Invoice.objects.filter(payment=payment).exists():
        return Invoice.objects.get(payment=payment)
    user = payment.user
    gst_rate = config.default_gst_rate if config.default_gst_rate is not None else Decimal('0')
    amount = payment.amount  # rupees
    if gst_rate and float(gst_rate) > 0:
        # Taxable = amount / (1 + gst/100); tax = amount - taxable; CGST = SGST = tax/2
        gst_divisor = 1 + float(gst_rate) / 100
        taxable_value = Decimal(str(round(amount / gst_divisor, 2)))
        tax = Decimal(str(amount)) - taxable_value
        cgst = sgst = tax / 2
    else:
        taxable_value = Decimal(str(amount))
        cgst = sgst = Decimal('0')
    invoice_number = _next_invoice_number(config)
    # Use gateway payment id (pay_xxx) as transaction ID on receipt; fallback to order id then internal id
    transaction_id = payment.gateway_payment_id or payment.gateway_order_id or 'pay-{}'.format(payment.id)
    service_label = config.get_service_label(payment.obj_type)
    address_parts = []
    if getattr(user, 'user_profile', None):
        try:
            up = user.user_profile
            if getattr(up, 'address', None):
                address_parts.append(up.address)
        except Exception:
            pass
    customer_address = ', '.join(filter(None, address_parts)) or '-'
    invoice = Invoice.objects.create(
        payment=payment,
        invoice_number=invoice_number,
        transaction_id=transaction_id,
        service=service_label,
        service_obj_type=payment.obj_type,
        amount=amount,
        currency=payment.currency,
        gst_rate=gst_rate,
        taxable_value=taxable_value,
        cgst=cgst,
        sgst=sgst,
        customer_name=user.name or user.email or '-',
        customer_email=user.email or '',
        customer_address=customer_address,
    )
    _generate_pdf_and_send_emails(invoice, config)
    return invoice


def _next_invoice_number(config):
    """Return numeric invoice id: YYMMDD + 5-digit serial (e.g. 25021200001)."""
    from django.utils import timezone
    now = timezone.now()
    yymmdd = now.strftime('%y%m%d')  # 6 digits: yy mm dd
    num = config.invoice_next_number
    config.invoice_next_number = num + 1
    config.save(update_fields=['invoice_next_number', 'modified'])
    return '{}{:05d}'.format(yymmdd, num)


def _generate_pdf_and_send_emails(invoice, config=None):
    """Generate invoice PDF, save to invoice. Send one email to customer with BCC to admin; if no customer send, send to admin only."""
    if config is None:
        config = get_config()
    html = _render_invoice_html(invoice, config)
    pdf_bytes = _html_to_pdf(html)
    if pdf_bytes:
        fname = 'invoice_{}.pdf'.format(invoice.invoice_number.replace('/', '-'))
        invoice.invoice_pdf.save(fname, ContentFile(pdf_bytes), save=True)
    # Send to customer with BCC to admin (one email), or to admin only if no customer send
    if config.auto_send_invoice_to_customer and invoice.customer_email:
        bcc_list = [config.accounts_email] if config.accounts_email else []
        _send_invoice_email_to_customer_with_bcc(
            invoice,
            invoice.customer_email,
            bcc_list=bcc_list,
            pdf_bytes=pdf_bytes,
        )
    elif config.accounts_email:
        _send_invoice_email(
            invoice,
            config.accounts_email,
            InvoiceEmailLog.RECIPIENT_ADMIN,
            pdf_bytes,
        )


def _render_invoice_html(invoice, config):
    """Render Indian GST invoice HTML. Use Django engine (invoice template uses Django syntax)."""
    from django.template import engines
    ctx = {
        'invoice': invoice,
        'config': config,
        'invoice_date': invoice.created,
    }
    django_engine = engines['django']
    template = django_engine.get_template('invoices/gst_invoice_pdf.html')
    return template.render(ctx)


def _html_to_pdf(html):
    """Convert HTML to PDF bytes using weasyprint."""
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        return pdf_bytes
    except Exception as e:
        import traceback
        print('Invoice PDF generation failed:', e)
        traceback.print_exc()
        return None


def _send_invoice_email_to_customer_with_bcc(invoice, to_email, bcc_list=None, pdf_bytes=None):
    """Send one invoice email to customer with BCC to admin; log both customer and admin (BCC) sends."""
    from django.core.mail import EmailMultiAlternatives
    bcc_list = bcc_list or []
    subject = 'Invoice {} - {}'.format(invoice.invoice_number, invoice.service)
    body = 'Please find your invoice attached.\n\nTransaction ID: {}\nAmount: ₹ {}\n\nThank you.'.format(
        invoice.transaction_id, invoice.amount
    )
    log_customer = InvoiceEmailLog.objects.create(
        invoice=invoice,
        recipient_type=InvoiceEmailLog.RECIPIENT_CUSTOMER,
        recipient_email=to_email,
        success=False,
    )
    log_admin = None
    if bcc_list:
        log_admin = InvoiceEmailLog.objects.create(
            invoice=invoice,
            recipient_type=InvoiceEmailLog.RECIPIENT_ADMIN,
            recipient_email=bcc_list[0],
            success=False,
        )
    try:
        # Use DEFAULT_FROM_EMAIL so From has display name (e.g. "Topteen <noreply@...>") for better inbox delivery
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'TOPTEEN_FROM_EMAIL', '')
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
            bcc=bcc_list,
        )
        # Reply-To so replies go to accounts; helps deliverability and support
        if bcc_list:
            email.reply_to = [bcc_list[0]]
        if pdf_bytes:
            email.attach('invoice_{}.pdf'.format(invoice.invoice_number), pdf_bytes, 'application/pdf')
        email.send(fail_silently=False)
        CommunicationLog.objects.create(
            to="{},{}".format(to_email, ",".join(bcc_list)) if bcc_list else to_email,
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="success",
        )
        log_customer.success = True
        log_customer.save(update_fields=['success', 'modified'])
        if log_admin:
            log_admin.success = True
            log_admin.save(update_fields=['success', 'modified'])
    except Exception as e:
        CommunicationLog.objects.create(
            to="{},{}".format(to_email, ",".join(bcc_list)) if bcc_list else to_email,
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="failed: {}".format(e),
        )
        log_customer.error_message = str(e)
        log_customer.save(update_fields=['error_message', 'modified'])
        if log_admin:
            log_admin.error_message = str(e)
            log_admin.save(update_fields=['error_message', 'modified'])


def _send_invoice_email(invoice, to_email, recipient_type, pdf_bytes):
    """Send invoice email and log result."""
    from django.core.mail import EmailMultiAlternatives
    subject = 'Invoice {} - {}'.format(invoice.invoice_number, invoice.service)
    body = 'Please find your invoice attached.\n\nTransaction ID: {}\nAmount: ₹ {}\n\nThank you.'.format(
        invoice.transaction_id, invoice.amount
    )
    log = InvoiceEmailLog.objects.create(
        invoice=invoice,
        recipient_type=recipient_type,
        recipient_email=to_email,
        success=False,
    )
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'TOPTEEN_FROM_EMAIL', '')
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
        )
        if pdf_bytes:
            email.attach('invoice_{}.pdf'.format(invoice.invoice_number), pdf_bytes, 'application/pdf')
        email.send(fail_silently=False)
        CommunicationLog.objects.create(
            to=to_email,
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="success",
        )
        log.success = True
        log.save(update_fields=['success', 'modified'])
    except Exception as e:
        CommunicationLog.objects.create(
            to=to_email,
            body=subject,
            type=choices.CommunicationTypeChooices.EMAIL,
            response="failed: {}".format(e),
        )
        log.error_message = str(e)
        log.save(update_fields=['error_message', 'modified'])


def ensure_invoice_pdf(invoice):
    """
    Ensure invoice has a PDF file; generate on-the-fly if missing.
    Returns (pdf_bytes, None) on success, or (None, error_message) on failure.
    """
    if invoice.invoice_pdf:
        try:
            with invoice.invoice_pdf.open('rb') as f:
                return f.read(), None
        except (ValueError, OSError):
            pass
    config = get_config()
    html = _render_invoice_html(invoice, config)
    pdf_bytes = _html_to_pdf(html)
    if not pdf_bytes:
        return None, 'PDF generation failed (e.g. weasyprint not available).'
    fname = 'invoice_{}.pdf'.format((invoice.invoice_number or str(invoice.id)).replace('/', '-'))
    invoice.invoice_pdf.save(fname, ContentFile(pdf_bytes), save=True)
    return pdf_bytes, None


def resend_invoice_email(invoice, recipient_type):
    """Resend invoice email to admin or customer and log."""
    config = get_config()
    if recipient_type == InvoiceEmailLog.RECIPIENT_ADMIN:
        to_email = config.accounts_email
    else:
        to_email = invoice.customer_email
    if not to_email:
        return False, 'No email address'
    pdf_bytes, _ = ensure_invoice_pdf(invoice)
    if not pdf_bytes:
        return False, 'Could not generate or read invoice PDF'
    _send_invoice_email(invoice, to_email, recipient_type, pdf_bytes)
    return True, None
