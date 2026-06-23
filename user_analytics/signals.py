"""
Django signals to automatically track business events.
These signals automatically create UserEvent records when specific actions occur.
"""
from django.db.models.signals import post_save, post_delete
from django.db import transaction
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.contrib.contenttypes.models import ContentType
from users.models import User
from payments.models import Payment
from psychometric_tests.models import PsychometricTestPayment, CandidateTest
from skilllab.models import SkilllabCoursePayment
from institute.models import StudentManagement
from user_analytics.tasks import (
    safe_track_user_event,
    track_user_event_sync,
    link_analytics_session_to_user,
)
from core import choices
import logging

logger = logging.getLogger(__name__)


def _get_user_source_context(user):
    """
    Resolve best-effort session/source attribution for business events.
    Returns (session_id, source_name, enquiry_source_id).
    enquiry_source_id is set when attribution came from a ?ref= EnquirySource row.
    """
    session_id = None
    source_name = 'Direct'
    enquiry_source_id = None
    try:
        from user_analytics.models import UserActivity, UserJourney

        recent_activity = (
            UserActivity.objects.filter(user=user, enquiry_source__isnull=False)
            .select_related('enquiry_source')
            .order_by('-created')
            .first()
        )
        if not recent_activity:
            recent_activity = (
                UserActivity.objects.filter(user=user)
                .select_related('enquiry_source')
                .order_by('-created')
                .first()
            )
        if recent_activity:
            session_id = recent_activity.session_id or session_id
            if getattr(recent_activity, 'enquiry_source_id', None) and recent_activity.enquiry_source:
                source_name = recent_activity.enquiry_source.name
                enquiry_source_id = recent_activity.enquiry_source_id
            else:
                source_name = (
                    (recent_activity.utm_source and recent_activity.utm_source.strip()) or
                    (recent_activity.traffic_source_category and recent_activity.traffic_source_category.strip()) or
                    source_name
                )

        if not session_id:
            recent_journey = (
                UserJourney.objects.filter(user=user, enquiry_source__isnull=False)
                .select_related('enquiry_source')
                .order_by('-start_time')
                .first()
            )
            if not recent_journey:
                recent_journey = (
                    UserJourney.objects.filter(user=user)
                    .select_related('enquiry_source')
                    .order_by('-start_time')
                    .first()
                )
            if recent_journey:
                session_id = recent_journey.session_id or session_id
                if getattr(recent_journey, 'enquiry_source_id', None) and recent_journey.enquiry_source:
                    source_name = recent_journey.enquiry_source.name
                    enquiry_source_id = recent_journey.enquiry_source_id
                else:
                    source_name = (
                        (recent_journey.utm_source and recent_journey.utm_source.strip()) or
                        (recent_journey.traffic_source_category and recent_journey.traffic_source_category.strip()) or
                        source_name
                    )
    except Exception:
        pass
    return session_id, source_name, enquiry_source_id


@receiver(post_save, sender=User)
def track_user_registration(sender, instance, created, **kwargs):
    """
    Track user registration event.
    """
    if created:
        try:
            def _track_registration():
                session_id, source_name, enq_id = _get_user_source_context(instance)
                meta = {
                    'email': instance.email,
                    'name': instance.name,
                    'user_type': instance.get_user_type_display() if hasattr(instance, 'get_user_type_display') else 'Unknown',
                    'source': source_name,
                }
                if enq_id:
                    meta['enquiry_source_id'] = enq_id
                # Keep registration tracking synchronous so analytics is reliable
                # even when Celery workers are stale/unavailable.
                out = track_user_event_sync(
                    event_type='registration',
                    event_name='User Registered',
                    user_id=instance.id,
                    event_value=0,
                    session_id=session_id,
                    metadata=meta,
                )
                if out:
                    logger.info(f"Tracked user registration for user {instance.id}")
                else:
                    logger.error(
                        "Registration event tracking returned no result for user %s",
                        instance.id,
                    )
                try:
                    from notifications.models import NotificationCategory
                    from notifications.services import emit_notification

                    recipients = list(
                        User.objects.filter(
                            user_type=choices.UserType.MARKETINGGROUPADMIN,
                            is_active=True,
                        )
                    )
                    if recipients:
                        emit_notification(
                            event_type='accounts.new_registration',
                            title='New registration',
                            body='User {0} ({1}) registered from {2}.'.format(
                                instance.name or '-',
                                instance.email,
                                source_name,
                            ),
                            recipients=recipients,
                            category=NotificationCategory.MARKETING,
                            source_obj=instance,
                            payload={
                                'user_id': instance.id,
                                'email': instance.email,
                            },
                            dedupe_key='accounts_registration_{}'.format(instance.id),
                        )
                except Exception as notify_exc:
                    logger.warning(
                        'Could not emit registration notification for user %s: %s',
                        instance.id,
                        notify_exc,
                    )
            transaction.on_commit(_track_registration)
        except Exception as e:
            logger.error(f"Error tracking user registration: {e}", exc_info=True)


@receiver(post_save, sender=Payment)
def track_payment_event(sender, instance, created, **kwargs):
    """
    Track payment events (success, failure, pending).
    Note: For psychometric test payments, the PsychometricTestPayment model also creates events
    with more detailed test type information. This Payment event is kept for gateway tracking.
    """
    try:
        # Skip creating event if this is a psychometric test payment
        # The PsychometricTestPayment signal will handle it with better metadata
        if instance.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
            # Check if PsychometricTestPayment exists and will create its own event
            try:
                from psychometric_tests.models import PsychometricTestPayment
                psych_payment = PsychometricTestPayment.objects.filter(id=instance.obj_id).first()
                if psych_payment:
                    # Skip Payment event - PsychometricTestPayment signal will handle it
                    logger.debug(f"Skipping Payment event {instance.id} - PsychometricTestPayment {psych_payment.id} will create event")
                    return
            except Exception:
                pass  # Continue with Payment event if we can't check
        
        # Determine event type based on payment status
        if instance.is_success == choices.YesNoChoices.YES:
            event_type = 'payment_success'
            event_name = f'Payment Success - {instance.get_obj_type_display()}'
            # Payment.amount is whole rupees (BaseMoneyModel).get_display_price()
            event_value = float(instance.amount) if hasattr(instance, 'amount') and instance.amount else 0
            payment_stage = 'paid'
        else:
            # Check if this is a new payment (pending) or failed
            if created:
                event_type = 'payment_pending'
                event_name = f'Payment Pending - {instance.get_obj_type_display()}'
                payment_stage = 'checkout_started'
            else:
                event_type = 'payment_failed'
                event_name = f'Payment Failed - {instance.get_obj_type_display()}'
                payment_stage = 'gateway_error'
            # Keep attempted amount for analytics display (same unit as success: whole rupees).
            event_value = float(instance.amount) if hasattr(instance, 'amount') and instance.amount else 0
        
        content_type = ContentType.objects.get_for_model(instance)
        
        # Build metadata
        metadata = {
            'gateway': instance.get_gateway_display() if hasattr(instance, 'get_gateway_display') else 'Unknown',
            'obj_type': instance.get_obj_type_display(),
            'obj_id': instance.obj_id,
            'gateway_order_id': instance.gateway_order_id or '',
            'payment_stage': payment_stage,
            'order_amount_rupees': float(instance.amount) if getattr(instance, 'amount', None) else 0.0,
        }
        
        # If this is a psychometric test payment, try to get test type info
        if instance.obj_type == choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL:
            try:
                from psychometric_tests.models import PsychometricTestPayment
                psych_payment = PsychometricTestPayment.objects.filter(id=instance.obj_id).first()
                if psych_payment:
                    metadata['test_type'] = psych_payment.get_test_type_display()
                    metadata['test_name'] = psych_payment.get_test_name()
                    # Update event name to include test type
                    event_name = f'Payment Success - {psych_payment.get_test_name()}'
            except Exception:
                pass
        
        session_id, source_name, _enq = _get_user_source_context(instance.user)
        metadata['source'] = source_name
        
        safe_track_user_event(
            event_type=event_type,
            event_name=event_name,
            user_id=instance.user.id,
            event_value=event_value,
            content_type_id=content_type.id,
            object_id=instance.id,
            session_id=session_id,
            metadata=metadata
        )
        logger.info(f"Tracked payment event: {event_type} for payment {instance.id}")
    except Exception as e:
        logger.error(f"Error tracking payment event: {e}", exc_info=True)


@receiver(post_save, sender=PsychometricTestPayment)
def track_psychometric_payment(sender, instance, created, **kwargs):
    """
    Track psychometric test payment events.
    Also tracks test started event when payment is successful.
    """
    try:
        session_id, source, _enq = _get_user_source_context(instance.user)
        
        if instance.is_success == choices.YesNoChoices.YES:
            event_type = 'payment_success'
            event_name = f'Psychometric Test Payment - {instance.get_test_name()}'
            # Same as Payment.amount — whole rupees
            event_value = float(instance.amount) if hasattr(instance, 'amount') and instance.amount else 0
        else:
            event_type = 'payment_pending' if created else 'payment_failed'
            event_name = f'Psychometric Test Payment - {instance.get_test_name()}'
            event_value = float(instance.amount) if hasattr(instance, 'amount') and instance.amount else 0
        
        content_type = ContentType.objects.get_for_model(instance)
        
        # Track payment event (include traffic source for reporting)
        psych_meta = {
            'test_type': instance.get_test_type_display(),
            'test_name': instance.get_test_name(),
            'source': source,
            'order_amount_rupees': float(instance.amount) if getattr(instance, 'amount', None) else 0.0,
        }
        if event_type == 'payment_pending':
            psych_meta['payment_stage'] = 'checkout_started'
            psych_meta['stage'] = 'started'
        if event_type == 'payment_failed':
            psych_meta['payment_stage'] = 'gateway_error'
        safe_track_user_event(
            event_type=event_type,
            event_name=event_name,
            user_id=instance.user.id,
            event_value=event_value,
            content_type_id=content_type.id,
            object_id=instance.id,
            session_id=session_id,
            metadata=psych_meta,
        )
        
        # If payment is successful, also track test started event
        if instance.is_success == choices.YesNoChoices.YES:
            safe_track_user_event(
                event_type='psychometric_test_started',
                event_name=f'Psychometric Test Started - {instance.get_test_name()}',
                user_id=instance.user.id,
                event_value=0,
                content_type_id=content_type.id,
                object_id=instance.id,
                session_id=session_id,
                metadata={
                    'test_type': instance.get_test_type_display(),
                    'test_name': instance.get_test_name(),
                }
            )
    except Exception as e:
        logger.error(f"Error tracking psychometric payment: {e}", exc_info=True)


@receiver(post_save, sender=CandidateTest)
def track_psychometric_test_completion(sender, instance, created, **kwargs):
    """
    Track psychometric test completion and result generation.
    """
    if instance.is_success == choices.YesNoChoices.YES and not created:
        try:
            payment = instance.pyschometric_test_payment
            if payment:
                session_id, source_name, _enq = _get_user_source_context(payment.user)
                
                content_type = ContentType.objects.get_for_model(instance)
                
                # Track test completion
                safe_track_user_event(
                    event_type='psychometric_test_completed',
                    event_name=f'Psychometric Test Completed - {payment.get_test_name()}',
                    user_id=payment.user.id,
                    event_value=0,
                    content_type_id=content_type.id,
                    object_id=instance.id,
                    session_id=session_id,
                    metadata={
                        'test_type': payment.get_test_type_display(),
                        'test_name': payment.get_test_name(),
                        'assessment_id': instance.assessment_id,
                        'source': source_name,
                    }
                )
                
                # Track result generation (if result exists)
                if hasattr(instance, 'result') and instance.result:
                    safe_track_user_event(
                        event_type='result_generated',
                        event_name=f'Psychometric Test Result Generated - {payment.get_test_name()}',
                        user_id=payment.user.id,
                        event_value=0,
                        content_type_id=content_type.id,
                        object_id=instance.id,
                        session_id=session_id,
                        metadata={
                            'test_type': payment.get_test_type_display(),
                            'test_name': payment.get_test_name(),
                            'assessment_id': instance.assessment_id,
                            'source': source_name,
                        }
                    )
                
                logger.info(f"Tracked psychometric test completion for user {payment.user.id}")
        except Exception as e:
            logger.error(f"Error tracking psychometric test completion: {e}", exc_info=True)


@receiver(post_save, sender=SkilllabCoursePayment)
def track_skilllab_enrollment(sender, instance, created, **kwargs):
    """
    Track SkillLab course enrollment.
    """
    if instance.is_success == choices.YesNoChoices.YES:
        try:
            content_type = ContentType.objects.get_for_model(instance)
            
            session_id, source_name, _enq = _get_user_source_context(instance.user)
            safe_track_user_event(
                event_type='skilllab_enrolled',
                event_name='SkillLab Course Enrolled',
                user_id=instance.user.id,
                event_value=float(instance.amount) if hasattr(instance, 'amount') else 0,
                content_type_id=content_type.id,
                object_id=instance.id,
                session_id=session_id,
                metadata={
                    'course_id': instance.skilllab_course.id if instance.skilllab_course else None,
                    'course_name': instance.skilllab_course.title if instance.skilllab_course else 'Unknown',
                    'source': source_name,
                }
            )
        except Exception as e:
            logger.error(f"Error tracking SkillLab enrollment: {e}", exc_info=True)


@receiver(post_save, sender=StudentManagement)
def track_institute_student_registration(sender, instance, created, **kwargs):
    """
    Track institute student registration.
    """
    if created:
        try:
            session_id, source_name, _enq = (
                _get_user_source_context(instance.student)
                if instance.student
                else (None, 'Direct', None)
            )
            
            content_type = ContentType.objects.get_for_model(instance)
            
            safe_track_user_event(
                event_type='institute_student_registered',
                event_name='Institute Student Registered',
                user_id=instance.student.id if instance.student else None,
                event_value=0,
                content_type_id=content_type.id,
                object_id=instance.id,
                session_id=session_id,
                metadata={
                    'institute_id': instance.institute.id if hasattr(instance, 'institute') and instance.institute else None,
                    'class_section': str(instance.class_and_section) if hasattr(instance, 'class_and_section') and instance.class_and_section else None,
                    'source': source_name,
                }
            )
        except Exception as e:
            logger.error(f"Error tracking institute student registration: {e}", exc_info=True)


@receiver(user_logged_in)
def link_session_on_login(sender, request, user, **kwargs):
    """Link anonymous analytics rows to the authenticated user on login."""
    try:
        session_id = request.session.get('analytics_session_id') if request else None
        if session_id and user:
            link_analytics_session_to_user(session_id, user)
    except Exception:
        pass


@receiver(user_logged_in)
def apply_session_expiry_on_login(sender, request, user, **kwargs):
    """
    Ensure session cookie lifetime is set for every login path (social OAuth, admin, etc.).
    login_user_with_session() sets pending flags and applies expiry after this signal runs.
    """
    if not request:
        return
    try:
        if request.session.get("_pending_remember_me") or request.session.get(
            "_pending_demo_login"
        ):
            return
        from users.session_utils import apply_login_session_expiry

        apply_login_session_expiry(request)
        request.session.modified = True
    except Exception:
        pass

