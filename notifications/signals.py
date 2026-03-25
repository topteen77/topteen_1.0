from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core import choices
from institute.models import StudentManagement
from payments.models import Payment
from user_analytics.models import UserEvent
from user_analytics.models import Lead

from .models import NotificationCategory
from .services import (
    emit_notification,
    get_admin_and_accounts_users,
    get_parent_users_for_student,
)


@receiver(post_save, sender=Payment)
def payment_notifications(sender, instance, created, **kwargs):
    if not instance.user_id:
        return

    recipients = [instance.user]
    recipients.extend(list(get_parent_users_for_student(instance.user_id)))
    staff = list(get_admin_and_accounts_users())

    previous_is_success = getattr(instance, '_previous_is_success', None)
    became_success = instance.is_success == choices.YesNoChoices.YES and (created or previous_is_success != choices.YesNoChoices.YES)
    became_failed = instance.is_success != choices.YesNoChoices.YES and (created or previous_is_success == choices.YesNoChoices.YES)

    if became_success:
        emit_notification(
            event_type='payment.success',
            title='Payment successful',
            body='Your payment was received successfully.',
            recipients=recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=instance,
            payload={'payment_id': instance.id, 'gateway_order_id': instance.gateway_order_id or ''},
            dedupe_key='payment_success_{}'.format(instance.id),
        )
        emit_notification(
            event_type='payment.status_updated',
            title='Payment status updated',
            body='Payment {} is marked successful.'.format(instance.id),
            recipients=staff,
            category=NotificationCategory.PAYMENT,
            source_obj=instance,
            payload={'payment_id': instance.id, 'status': 'success'},
            dedupe_key='payment_status_updated_success_{}'.format(instance.id),
        )
    elif became_failed:
        emit_notification(
            event_type='payment.failed',
            title='Payment failed',
            body='We could not confirm your payment. Please retry or contact support.',
            recipients=recipients,
            category=NotificationCategory.PAYMENT,
            source_obj=instance,
            payload={'payment_id': instance.id, 'gateway_order_id': instance.gateway_order_id or ''},
            dedupe_key='payment_failed_{}'.format(instance.id),
        )


@receiver(pre_save, sender=Payment)
def payment_notification_state_cache(sender, instance, **kwargs):
    """
    Cache previous payment state to emit notifications only on status transition.
    """
    if not instance.pk:
        instance._previous_is_success = None
        return
    prev = sender.objects.filter(pk=instance.pk).values_list('is_success', flat=True).first()
    instance._previous_is_success = prev


@receiver(post_save, sender=StudentManagement)
def institute_student_notifications(sender, instance, created, **kwargs):
    if not created or not instance.institute_id:
        return
    institute_user = getattr(instance.institute, 'created_by', None)
    recipients = [u for u in [institute_user] if getattr(u, 'id', None)]
    if not recipients:
        return
    emit_notification(
        event_type='institute.student_registered',
        title='New student registered',
        body='A student was registered under your institute.',
        recipients=recipients,
        category=NotificationCategory.INSTITUTE,
        source_obj=instance,
        payload={'student_id': instance.student_id, 'institute_id': instance.institute_id},
        dedupe_key='institute_student_registered_{}'.format(instance.id),
    )


@receiver(post_save, sender=Lead)
def marketing_lead_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    from users.models import User

    recipients = list(
        User.objects.filter(
            user_type=choices.UserType.MARKETINGGROUPADMIN,
            is_active=True,
        )
    )
    if not recipients:
        return
    emit_notification(
        event_type='marketing.new_lead',
        title='New lead captured',
        body='Lead {} ({}) captured from {}.'.format(instance.name or '-', instance.email, instance.source or 'unknown'),
        recipients=recipients,
        category=NotificationCategory.MARKETING,
        source_obj=instance,
        payload={'lead_id': instance.id, 'email': instance.email, 'source': instance.source},
        dedupe_key='marketing_new_lead_{}'.format(instance.id),
    )


@receiver(post_save, sender=UserEvent)
def userevent_payment_failed_notifications(sender, instance, created, **kwargs):
    """
    Fallback path: some gateway failures are only tracked as UserEvent(payment_failed).
    Ensure student/parent still receive an in-app notification in those flows.
    """
    if not created or instance.event_type != 'payment_failed' or not instance.user_id:
        return

    recipients = [instance.user]
    recipients.extend(list(get_parent_users_for_student(instance.user_id)))

    metadata = instance.metadata or {}
    payment_id = metadata.get('payment_id') or instance.object_id
    gateway_order_id = metadata.get('gateway_order_id') or ''
    reason = (metadata.get('payment_stage') or metadata.get('error_message') or '').strip()
    body = 'We could not confirm your payment. Please retry or contact support.'
    if reason:
        body = '{} Reason: {}.'.format(body, reason)

    dedupe_key = 'payment_failed_event_{}'.format(instance.id)
    if payment_id:
        # Keep same key shape as Payment signal to avoid duplicates for same payment.
        dedupe_key = 'payment_failed_{}'.format(payment_id)
    elif gateway_order_id:
        dedupe_key = 'payment_failed_order_{}'.format(gateway_order_id)

    emit_notification(
        event_type='payment.failed',
        title='Payment failed',
        body=body,
        recipients=recipients,
        category=NotificationCategory.PAYMENT,
        source_obj=instance if instance.object_id else None,
        payload={
            'payment_id': payment_id or '',
            'gateway_order_id': gateway_order_id,
            'event_id': instance.id,
        },
        dedupe_key=dedupe_key,
    )

