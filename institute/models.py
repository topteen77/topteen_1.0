from decimal import Decimal
from django.db import models
from core import choices
from core.models import BaseModel,SlugModel
from users.models import User
from psychometric_tests.models import PsychometricTestResult,PsychometricTestPayment,CandidateTest

from app.models import TestCompletion, Results
from core.models import Configuration
from psychometric_tests.task import create_central_test_candidate
from django.db.models import Sum
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# Create your models here.

def get_global_remain_credits():
        credits=Institute.objects.aggregate(sum=Sum("credit_counts"))
        global_credits=settings.CREDIT_LIMIT
        if credits['sum'] is not None:
            remain_credit=global_credits-credits['sum']
        else:
            remain_credit=global_credits
        return remain_credit

def credit_validator(value):
    credits=Institute.objects.aggregate(sum=Sum("credit_counts"))
    global_credits=settings.CREDIT_LIMIT
    remain_credit=global_credits-credits['sum']
    if value>=remain_credit:
        raise ValidationError(_("Value must be less than {}".format(remain_credit)))

class InstituteGroup(BaseModel):
    group_name=models.CharField(max_length=250)
    institute_group_admin=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="institute_group",limit_choices_to={'user_type':choices.UserType.INSTITUTEGROUPADMIN})

    def __str__(self):
        return self.group_name
    
class InstituteMarketingGroup(BaseModel):
    m_group_name = models.CharField(max_length=250)
    marketing_group_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketing_group",
        limit_choices_to={'user_type': choices.UserType.MARKETINGGROUPADMIN}  # Changed from MARKETING to MARKETINGGROUPADMIN
    )

    def __str__(self):
        return self.m_group_name


def get_default_marketing_group_for_direct_registration():
    """
    Marketing group for institutes that register without selecting a marketing partner.
    Uses settings.DEFAULT_DIRECT_INSTITUTE_MARKETING_ADMIN_USER_ID (marketing user, e.g. 1409).
    Returns None if the setting is 0/unset or the user does not exist or is not a marketing admin.
    """
    uid = getattr(settings, 'DEFAULT_DIRECT_INSTITUTE_MARKETING_ADMIN_USER_ID', None)
    if uid in (None, 0):
        return None
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    try:
        admin_user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        return None
    if admin_user.user_type != choices.UserType.MARKETINGGROUPADMIN:
        return None
    mg = InstituteMarketingGroup.objects.filter(
        marketing_group_admin=admin_user
    ).order_by('id').first()
    if mg:
        return mg
    return InstituteMarketingGroup.objects.create(
        m_group_name=(admin_user.name or admin_user.email or 'Default direct registrations')[:250],
        marketing_group_admin=admin_user,
    )


def resolve_marketing_group_for_public_registration(selected_group):
    """
    If the signup form chose a marketing group, keep it. Otherwise attach the default direct pool.
    """
    if selected_group is not None:
        return selected_group
    return get_default_marketing_group_for_direct_registration()


def institute_status_for_creator(creator):
    """
    Institutes created by marketing / institute-group admins or staff are approved immediately.
    Public self-registration and institute-owned signups stay pending.
    """
    if not creator or not getattr(creator, "is_authenticated", False):
        return choices.InstituteStatus.PENDING
    if creator.is_superuser or getattr(creator, "is_staff", False):
        return choices.InstituteStatus.APPROVED
    ut = getattr(creator, "user_type", None)
    if ut in (
        choices.UserType.MARKETINGGROUPADMIN,
        choices.UserType.INSTITUTEGROUPADMIN,
    ):
        return choices.InstituteStatus.APPROVED
    return choices.InstituteStatus.PENDING


class Institute(BaseModel, SlugModel):
    """
    Model representing an educational institute.
    """
    name = models.CharField(
        max_length=500,
        verbose_name="Institute Name",
        help_text="Name of the educational institute"
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="institute_created",
        limit_choices_to={'user_type': choices.UserType.INSTITUTE},
        verbose_name="Created By"
    )
    logo = models.ImageField(
        upload_to="upload/institute/logo/",
        null=True,
        max_length=250,
        verbose_name="Institute Logo"
    )
    address = models.CharField(
        max_length=350,
        null=True,
        blank=True,
        verbose_name="Address"
    )
    contact_info = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name="Contact Information"
    )
    administrator_contact = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name="Administrator Contact"
    )
    credit_counts = models.PositiveIntegerField(
        default=0,
        validators=[credit_validator],
        verbose_name="Credit Count",
        help_text="Number of credits allocated to the institute"
    )
    assignment_credits = models.PositiveIntegerField(
        default=0,
        verbose_name="Assignment credits",
        help_text="Pool of credits consumed when assigning psychometric packages to students.",
    )
    psychometric_access_mode = models.CharField(
        max_length=20,
        choices=choices.PsychometricAccessMode.CHOICES,
        default=choices.PsychometricAccessMode.FULL_BUNDLE,
        verbose_name="Psychometric access mode",
    )
    institute_group = models.ForeignKey(
        InstituteGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institute",
        verbose_name="Institute Group"
    )
    marketing_group = models.ForeignKey(
        InstituteMarketingGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institute",
        verbose_name="Marketing Institute Group"
    )
    institute_type = models.SmallIntegerField(
        choices=choices.InstituteType.CHOICES,default=choices.InstituteType.COLLEGE,
        verbose_name="Institute Type"
    )

    institute_status = models.SmallIntegerField(
        choices=choices.InstituteStatus.CHOICES,
        default=choices.InstituteStatus.PENDING,
        verbose_name="institute Status",
        help_text="Current status of the institute"
    )

    is_demo_institute = models.BooleanField(
        default=False,
        verbose_name="Demo institute",
        help_text=_("Mark as demo institute (e.g. for display on institute demo login or filtering)."),
    )
    is_system_demo = models.BooleanField(
        default=False,
        editable=False,
        verbose_name="System demo",
        help_text=_("Set only by the system for the fixed demo dataset. Only such data can be reset. Do not edit."),
    )

    # Seat Capacity fields for streams
    pcm = models.PositiveIntegerField(
        default=100,
        verbose_name="PCM Seat Capacity",
        help_text="Seat capacity for PCM stream"
    )
    cbm = models.PositiveIntegerField(
        default=100,
        verbose_name="CBM Seat Capacity",
        help_text="Seat capacity for CBM stream"
    )
    comm = models.PositiveIntegerField(
        default=100,
        verbose_name="COMM Seat Capacity",
        help_text="Seat capacity for COMM stream"
    )
    hme = models.PositiveIntegerField(
        default=100,
        verbose_name="HME Seat Capacity",
        help_text="Seat capacity for HME stream"
    )
    hmb = models.PositiveIntegerField(
        default=100,
        verbose_name="HMB Seat Capacity",
        help_text="Seat capacity for HMB stream"
    )

    class Meta:
        verbose_name = "Institute"
        verbose_name_plural = "Institutes"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['address']),
        ]

    def __str__(self):
        """String representation of the Institute."""
        return self.name

    @property
    def tieup_form_initial(self):
        """Tie-up billing field defaults for marketing edit institute modal."""
        from institute.tieup_billing import get_tieup_billing_form_initial

        return get_tieup_billing_form_initial(self)

    def get_current_credits_count(self):
        """
        Calculate and return the current available credits.
        
        Returns:
            int: Number of remaining credits
        """
        sm = StudentManagement.objects.filter(institute=self).count()
        current_credits = self.credit_counts - sm
        return current_credits
    
    def is_valid_credit_count(self):
        """
        Check if the institute has valid credit count.
        
        Returns:
            bool: True if credit count is valid, False otherwise
        """
        sm = StudentManagement.objects.filter(institute=self).count()
        current_credits = self.credit_counts - sm
        return 0 < current_credits <= self.credit_counts

    def has_assignment_credits(self, amount):
        return int(self.assignment_credits or 0) >= int(amount or 0)

    def uses_package_psychometric_mode(self):
        from django.conf import settings
        if not getattr(settings, 'ENABLE_PSYCHOMETRIC_PACKAGES', False):
            return False
        return self.psychometric_access_mode == choices.PsychometricAccessMode.PACKAGE

    def get_enabled_psychometric_package_codes(self):
        """Package codes marketing assigned to this institute (empty = all active packages)."""
        from psychometric_tests.models import InstitutePackagePrice

        return list(
            InstitutePackagePrice.objects.filter(institute=self)
            .values_list('package__code', flat=True)
        )

    def get_psychometric_csv_package_choices(self):
        from institute.psychometric_packages import (
            get_package_choices_for_institute,
            institute_package_mode_active,
        )

        if not institute_package_mode_active(self):
            return []
        return get_package_choices_for_institute(self)

    def clean(self):
        """
        Custom validation for the Institute model.
        """
        super().clean()
        if self.credit_counts < 0:
            raise ValidationError({
                'credit_counts': 'Credit count cannot be negative.'
            })
        
class ClassAndSection(BaseModel):
    class_and_section=models.CharField(max_length=100,null=True,blank=True)
    stream=models.CharField(max_length=100,null=True,blank=True)

    def __str__(self):
        return self.class_and_section

class StudentManagement(BaseModel):
    institute=models.ForeignKey(Institute,null=True,on_delete=models.SET_NULL,related_name="student_management")
    student=models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name="student_management")
    class_and_section=models.ForeignKey(ClassAndSection,null=True,blank=True,on_delete=models.SET_NULL,related_name="student_management")

    # ForeignKey to Counselor Manish
    counselor = models.ForeignKey('counselor.Counselor', null=True, blank=True, on_delete=models.SET_NULL, related_name="student_management")

    def get_psychometric_result(self):
        return PsychometricTestResult.objects.filter(assessment__central_test_candidate__user=self.student)

    def get_test_result(self):
        test_res = Results.objects.filter(user=self.student)
        success_count = sum(1 for result in test_res if result.is_test_successful)
        return success_count
    
    def create_student_psychometric_test(self):
        user=self.student
        sm=StudentManagement.objects.filter(student=user).exists()
        if sm:
            gateway_receipt="Student_Psychometric_test_receipt_{}".format(user.id)
            amount=Configuration.get('EAZYPAY_PSYCHOMETRIC_TEST_AMOUNT',10,editable=True)
            test_type=choices.PsychometricTestType.BASIC
            test,_test=PsychometricTestPayment.objects.get_or_create(user=user,gateway_receipt=gateway_receipt,test_type=test_type,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
            test.is_success=choices.YesNoChoices.YES
            test.save()
            create_central_test_candidate.delay(test.id)

    def get_student_test_link(self):
        ct=CandidateTest.objects.filter(central_test_candidate__user=self.student)
        if ct.exists():
            return ct.last().test_link
        else:
            return "#"
        
    def get_school_student_id(self):
        """Unique identifier for school/institute. SCHOOL_STUDENT_ID_PREFIX as prefix, then student ID (e.g. SCH/TT002786 or SCH/ST/TT002786)."""
        from core.models import Configuration
        school_prefix = (Configuration.get('SCHOOL_STUDENT_ID_PREFIX', 'SCH', editable=True) or 'SCH').strip() or 'SCH'
        student_id = self.student.get_student_display_id() if self.student else str(self.id).zfill(6)
        return "{}/{}".format(school_prefix, student_id)

    def __str__(self):
        return f"Student: {self.student}"


_STUDENT_MANAGEMENT_SENTINEL = object()


def get_cached_student_management(user):
    """Return the user's StudentManagement (with class_and_section prefetched),
    memoized on the user instance.

    The student dashboard, context processor and several helpers each look this
    record up per request; caching it avoids the repeated identical query.
    Mirrors ``StudentManagement.objects.filter(student=user).first()`` (callers
    that only need existence should check ``is not None``).
    """
    if not user or getattr(user, 'pk', None) is None:
        return None
    cached = getattr(user, '_student_management_cache', _STUDENT_MANAGEMENT_SENTINEL)
    if cached is not _STUDENT_MANAGEMENT_SENTINEL:
        return cached
    sm = (
        StudentManagement.objects.filter(student=user)
        .select_related('class_and_section')
        .first()
    )
    try:
        user._student_management_cache = sm
    except Exception:
        pass
    return sm


class InstituteAccountDeletion(BaseModel):
    institute=models.ForeignKey(Institute,null=True,on_delete=models.SET_NULL,related_name="account_deletion")
    reason=models.CharField(max_length=500,null=True,blank=True)

class InstituteLog(BaseModel):
    institute=models.ForeignKey(Institute,on_delete=models.SET_NULL,null=True,related_name="institute_log")
    email=models.CharField(max_length=500,null=True,blank=True)
    students_counts=models.PositiveIntegerField(default=0)

    def get_created_students(self):
        stu_counts=self.students_counts-len(eval(self.email))
        if stu_counts<0:
            return 0
        else:
            return stu_counts


class InstituteDiscountCoupon(BaseModel):
    """B2B tie-up coupon scoped to an institute (ported from counselor_project DiscountCoupon)."""
    institute = models.ForeignKey(
        Institute, on_delete=models.CASCADE, related_name="discount_coupons"
    )
    marketing_group = models.ForeignKey(
        InstituteMarketingGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discount_coupons",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institute_coupons_created",
    )
    code = models.CharField(max_length=64, unique=True, db_index=True)
    discount_type = models.CharField(
        max_length=20,
        choices=choices.CouponDiscountType.CHOICES,
        default=choices.CouponDiscountType.PERCENT,
    )
    value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Percentage (e.g. 10) or fixed amount in INR",
    )
    applies_to = models.CharField(
        max_length=40,
        choices=choices.CouponAppliesTo.CHOICES,
        default=choices.CouponAppliesTo.ALL,
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Institute discount coupons"
        ordering = ("-created",)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.discount_type} {self.value})"


class InstituteTieUpOrder(BaseModel):
    institute = models.ForeignKey(
        Institute, on_delete=models.CASCADE, related_name="tieup_orders"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tieup_orders_created",
    )
    status = models.SmallIntegerField(
        choices=choices.TieUpOrderStatus.CHOICES,
        default=choices.TieUpOrderStatus.ACTIVE,
    )
    notes = models.TextField(blank=True, default="")
    coupon = models.ForeignKey(
        InstituteDiscountCoupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"Tie-up order #{self.pk} — {self.institute}"


class InstituteTieUpLineItem(BaseModel):
    order = models.ForeignKey(
        InstituteTieUpOrder, on_delete=models.CASCADE, related_name="line_items"
    )
    product_type = models.SmallIntegerField(choices=choices.TieUpProductType.CHOICES)
    psychometric_package = models.ForeignKey(
        'psychometric_tests.PsychometricPackage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tieup_line_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.SmallIntegerField(
        choices=choices.TieUpPaymentStatus.CHOICES,
        default=choices.TieUpPaymentStatus.PENDING,
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tieup_line_items",
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tieup_lines_received",
    )
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def save(self, *args, **kwargs):
        qty = int(self.quantity or 0)
        unit = self.unit_price or Decimal("0")
        self.line_subtotal = (Decimal(qty) * unit).quantize(Decimal("0.01"))
        disc = self.line_discount or Decimal("0")
        self.total_amount = max(
            self.line_subtotal - disc, Decimal("0")
        ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_product_type_display()} x{self.quantity}"