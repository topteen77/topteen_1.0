"""
Django signals to automatically track business events.
These signals automatically create UserEvent records when specific actions occur.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from users.models import User
from payments.models import Payment
from psychometric_tests.models import PsychometricTestPayment, CandidateTest
from skilllab.models import SkilllabCoursePayment
from institute.models import StudentManagement
from user_analytics.tasks import track_user_event_async
from core import choices
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def track_user_registration(sender, instance, created, **kwargs):
    """
    Track user registration event.
    """
    if created:
        try:
            # Get session ID if available (from request context)
            session_id = getattr(instance, '_analytics_session_id', None)
            
            track_user_event_async.delay(
                event_type='registration',
                event_name='User Registered',
                user_id=instance.id,
                event_value=0,
                session_id=session_id,
                metadata={
                    'email': instance.email,
                    'name': instance.name,
                    'user_type': instance.get_user_type_display() if hasattr(instance, 'get_user_type_display') else 'Unknown',
                }
            )
            logger.info(f"Tracked user registration for user {instance.id}")
        except Exception as e:
            logger.error(f"Error tracking user registration: {e}", exc_info=True)


@receiver(post_save, sender=Payment)
def track_payment_event(sender, instance, created, **kwargs):
    """
    Track payment events (success, failure, pending).
    """
    try:
        # Determine event type based on payment status
        if instance.is_success == choices.YesNoChoices.YES:
            event_type = 'payment_success'
            event_name = f'Payment Success - {instance.get_obj_type_display()}'
            event_value = float(instance.amount) if hasattr(instance, 'amount') else 0
        else:
            # Check if this is a new payment (pending) or failed
            if created:
                event_type = 'payment_pending'
                event_name = f'Payment Pending - {instance.get_obj_type_display()}'
            else:
                event_type = 'payment_failed'
                event_name = f'Payment Failed - {instance.get_obj_type_display()}'
            event_value = 0
        
        content_type = ContentType.objects.get_for_model(instance)
        
        track_user_event_async.delay(
            event_type=event_type,
            event_name=event_name,
            user_id=instance.user.id,
            event_value=event_value,
            content_type_id=content_type.id,
            object_id=instance.id,
            metadata={
                'gateway': instance.get_gateway_display() if hasattr(instance, 'get_gateway_display') else 'Unknown',
                'obj_type': instance.get_obj_type_display(),
                'obj_id': instance.obj_id,
                'gateway_order_id': instance.gateway_order_id or '',
            }
        )
        logger.info(f"Tracked payment event: {event_type} for payment {instance.id}")
    except Exception as e:
        logger.error(f"Error tracking payment event: {e}", exc_info=True)


@receiver(post_save, sender=PsychometricTestPayment)
def track_psychometric_payment(sender, instance, created, **kwargs):
    """
    Track psychometric test payment events.
    """
    try:
        if instance.is_success == choices.YesNoChoices.YES:
            event_type = 'payment_success'
            event_name = f'Psychometric Test Payment - {instance.get_test_name()}'
            event_value = float(instance.amount) if hasattr(instance, 'amount') else 0
        else:
            event_type = 'payment_pending' if created else 'payment_failed'
            event_name = f'Psychometric Test Payment - {instance.get_test_name()}'
            event_value = 0
        
        content_type = ContentType.objects.get_for_model(instance)
        
        track_user_event_async.delay(
            event_type=event_type,
            event_name=event_name,
            user_id=instance.user.id,
            event_value=event_value,
            content_type_id=content_type.id,
            object_id=instance.id,
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
    Track psychometric test completion.
    """
    if instance.is_success == choices.YesNoChoices.YES and not created:
        try:
            payment = instance.pyschometric_test_payment
            if payment:
                content_type = ContentType.objects.get_for_model(instance)
                
                track_user_event_async.delay(
                    event_type='psychometric_test_completed',
                    event_name=f'Psychometric Test Completed - {payment.get_test_name()}',
                    user_id=payment.user.id,
                    event_value=0,
                    content_type_id=content_type.id,
                    object_id=instance.id,
                    metadata={
                        'test_type': payment.get_test_type_display(),
                        'test_name': payment.get_test_name(),
                        'assessment_id': instance.assessment_id,
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
            
            track_user_event_async.delay(
                event_type='skilllab_enrolled',
                event_name='SkillLab Course Enrolled',
                user_id=instance.user.id,
                event_value=float(instance.amount) if hasattr(instance, 'amount') else 0,
                content_type_id=content_type.id,
                object_id=instance.id,
                metadata={
                    'course_id': instance.skilllab_course.id if instance.skilllab_course else None,
                    'course_name': instance.skilllab_course.title if instance.skilllab_course else 'Unknown',
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
            content_type = ContentType.objects.get_for_model(instance)
            
            track_user_event_async.delay(
                event_type='institute_student_registered',
                event_name='Institute Student Registered',
                user_id=instance.student.id if instance.student else None,
                event_value=0,
                content_type_id=content_type.id,
                object_id=instance.id,
                metadata={
                    'institute_id': instance.institute.id if hasattr(instance, 'institute') and instance.institute else None,
                    'class_section': str(instance.class_and_section) if hasattr(instance, 'class_and_section') and instance.class_and_section else None,
                }
            )
        except Exception as e:
            logger.error(f"Error tracking institute student registration: {e}", exc_info=True)

