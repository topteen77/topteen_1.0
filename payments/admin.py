from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils.html import format_html
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_display',
        'user_type_display',
        'is_test_payment',
        'amount_display',
        'gateway_display',
        'is_success_display',
        'obj_type_display',
        'gateway_order_id',
        'created',
    ]
    list_filter = ('is_test_payment', 'is_success', 'gateway', 'obj_type', 'created')
    list_editable = ('is_test_payment',)
    search_fields = (
        'user__email',
        'user__name',
        'user__mobile',
        'gateway_order_id',
        'gateway_payment_id',
        'gateway_receipt',
    )
    readonly_fields = (
        'user',
        'gateway_receipt',
        'gateway',
        'gateway_order_id',
        'gateway_payment_id',
        'gateway_signature',
        'is_success',
        'obj_id',
        'obj_type',
        'amount',
        'currency',
        'response_code',
        'transaction_amount',
        'transaction_date',
        'payment_mode',
        'created',
        'modified',
    )
    raw_id_fields = ('user',)
    list_select_related = ('user',)
    ordering = ('-created',)
    date_hierarchy = 'created'

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return obj.is_test_payment

    def delete_model(self, request, obj):
        if not obj.is_test_payment:
            raise PermissionDenied(
                'Actual payments cannot be deleted. Only testing payments (is_test_payment=True) can be deleted.'
            )
        obj.delete(hard_delete=True)
        self.message_user(request, f'Payment #{obj.id} has been permanently deleted.', messages.SUCCESS)

    def delete_queryset(self, request, queryset):
        deleted = 0
        skipped = 0
        for obj in queryset:
            if obj.is_test_payment:
                obj.delete(hard_delete=True)
                deleted += 1
            else:
                skipped += 1
        if deleted:
            self.message_user(
                request,
                f'{deleted} testing payment(s) permanently deleted.',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'{skipped} actual payment(s) were not deleted. Only testing payments can be deleted.',
                messages.WARNING,
            )

    def user_display(self, obj):
        if not obj.user:
            return '-'
        name = obj.user.name or obj.user.email or str(obj.user.id)
        return f'{name} (#{obj.user_id})'

    user_display.short_description = 'User'

    def user_type_display(self, obj):
        if not obj.user:
            return '-'
        return obj.user.get_user_type_display()

    user_type_display.short_description = 'Role'

    def amount_display(self, obj):
        return obj.get_display_price() if obj else '-'

    amount_display.short_description = 'Amount'

    def gateway_display(self, obj):
        return obj.get_gateway_display() if obj else '-'

    gateway_display.short_description = 'Gateway'

    def is_success_display(self, obj):
        if obj is None:
            return '-'
        if obj.is_success == 1:  # YesNoChoices.YES
            return format_html('<span style="color: green;">✓ Success</span>')
        return format_html('<span style="color: red;">Failed</span>')

    is_success_display.short_description = 'Status'

    def obj_type_display(self, obj):
        return obj.get_obj_type_display() if obj else '-'

    obj_type_display.short_description = 'Payment for'
