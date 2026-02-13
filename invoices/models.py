"""
Invoice system: system-generated GST invoice for every successful payment.
No invoice is generated for failed payments.
"""
from django.db import models
from django.conf import settings
from core.models import BaseModel
from core import choices


def invoice_pdf_upload_to(instance, filename):
    return 'invoices/{0}/{1}'.format(instance.id, filename)


class InvoiceConfiguration(BaseModel):
    """Singleton config for invoice generation. Managed by admin."""
    company_name = models.CharField(max_length=255, blank=True)
    company_address = models.TextField(blank=True)
    gstin = models.CharField(max_length=32, blank=True, verbose_name='GSTIN')
    accounts_email = models.EmailField(
        blank=True,
        help_text='Email address to receive every invoice copy'
    )
    auto_send_invoice_to_customer = models.BooleanField(
        default=True,
        help_text='Automatically email invoice to customer when payment succeeds'
    )
    generate_invoice_for_institute_students = models.BooleanField(
        default=False,
        help_text='If ON, invoices are generated and sent for institute-registered (free) students too. If OFF, no invoice for them.'
    )
    default_gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Default GST rate (e.g. 18 for 18%%). Leave blank for invoices without GST.'
    )
    invoice_prefix = models.CharField(max_length=20, default='INV', blank=True)
    invoice_next_number = models.PositiveIntegerField(default=1)
    # Custom service labels: stored as JSON { "10": "Stream Sorter", "20": "Skill Lab Course", "30": "Career Counsellor" }
    service_labels_json = models.TextField(
        blank=True,
        help_text='Optional JSON: {"10":"Stream Sorter","20":"Skill Lab","30":"Career Counsellor"}'
    )

    class Meta:
        verbose_name = 'Invoice / Accounts configuration'
        verbose_name_plural = 'Invoice / Accounts configuration'

    def __str__(self):
        return 'Invoice configuration'

    def get_service_label(self, obj_type):
        """Return custom label for Payment.obj_type or default."""
        import json
        if self.service_labels_json:
            try:
                labels = json.loads(self.service_labels_json)
                return labels.get(str(obj_type)) or self._default_service_label(obj_type)
            except Exception:
                pass
        return self._default_service_label(obj_type)

    @staticmethod
    def _default_service_label(obj_type):
        from core.choices import PaymentObjectType
        return {
            PaymentObjectType.PYSCHOMETRICTESTDETAIL: 'Psychometric Test',
            PaymentObjectType.SKILLLABCOURSE: 'Skill Lab Course',
            PaymentObjectType.COUNSELOR: 'Career Counsellor Course',
        }.get(obj_type, 'Service')


class PaymentGatewayHealth(BaseModel):
    """Tracks whether gateway callback URL is working. Red alert in Accounts if not."""
    RAZORPAY = 1
    ICICI_EAZYPAY = 2
    GATEWAY_CHOICES = (
        (RAZORPAY, 'Razorpay'),
        (ICICI_EAZYPAY, 'ICICI EazyPay'),
    )
    gateway = models.SmallIntegerField(choices=GATEWAY_CHOICES, unique=True)
    last_callback_at = models.DateTimeField(null=True, blank=True)
    last_callback_success = models.BooleanField(default=False)
    last_error_message = models.TextField(blank=True)
    callback_url = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Payment gateway callback health'
        verbose_name_plural = 'Payment gateway callback health'

    def __str__(self):
        return self.get_gateway_display()

    @property
    def is_working(self):
        return self.last_callback_success and self.last_callback_at


class Invoice(BaseModel):
    """One invoice per successful payment. Never created for failed payments."""
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    transaction_id = models.CharField(max_length=120, db_index=True)
    service = models.CharField(max_length=128)
    service_obj_type = models.SmallIntegerField(
        choices=choices.PaymentObjectType.CHOICES,
        null=True,
        blank=True
    )
    amount = models.PositiveIntegerField(help_text='Amount in rupees')
    currency = models.PositiveSmallIntegerField(
        choices=choices.Currency.CHOICES,
        default=choices.Currency.IND
    )
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_address = models.TextField(blank=True)
    invoice_pdf = models.FileField(
        upload_to=invoice_pdf_upload_to,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-created']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return self.invoice_number

    def get_amount_display(self):
        return '₹ {}'.format(self.amount)


class InvoiceEmailLog(BaseModel):
    """Log of each invoice email send. Used for resend and failure tracking."""
    RECIPIENT_ADMIN = 'admin'
    RECIPIENT_CUSTOMER = 'customer'
    RECIPIENT_CHOICES = (
        (RECIPIENT_ADMIN, 'Admin / Accounts'),
        (RECIPIENT_CUSTOMER, 'Customer'),
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='email_logs'
    )
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_CHOICES)
    recipient_email = models.EmailField()
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Invoice email log'
        verbose_name_plural = 'Invoice email logs'

    def __str__(self):
        return '{} to {} at {}'.format(
            self.recipient_type,
            self.recipient_email,
            self.created
        )
