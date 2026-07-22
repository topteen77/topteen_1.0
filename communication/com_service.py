
from django.conf import settings
from django.utils.crypto import get_random_string
import requests
import logging
from urllib.parse import urlencode
from core import choices
from .models import OTP,CommunicationLog
from django.core.mail import EmailMultiAlternatives
from core import email_strings, sms_strings
from communication.email_templates import render_transactional_email
from communication.email_layout import ensure_email_html_wrapped
from communication.utils import referral_url_without_scheme
# from edmissions.celery import app
from django.utils.safestring import mark_safe
from django.template.loader import get_template
from django.utils.html import strip_tags
from datetime import datetime,timedelta
from users.models import User
from django.urls import reverse

logger = logging.getLogger(__name__)


class ComService:
    _SERVICE_URL = settings.MOBILE_SMS_SERVICE
    # Use DEFAULT_FROM_EMAIL (has display name) for better inbox delivery; fallback to TOPTEEN_FROM_EMAIL
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'TOPTEEN_FROM_EMAIL', '')

    def generate_otp(self):
        return get_random_string(6, allowed_chars='0123456789')

    def format_phone_number_with_country_code(self, phone_number):
        """
        Format phone number with country code if needed.
        For Indian numbers (10 digits starting with 6-9), prepend 91 (country code).
        If number already has country code, return as is.
        
        Args:
            phone_number: Phone number as int or string
            
        Returns:
            Formatted phone number string with country code (without + sign for API use)
        """
        # Convert to string and remove any spaces or special characters
        phone_str = str(phone_number).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Remove leading + if present
        if phone_str.startswith('+'):
            phone_str = phone_str[1:]
        
        # If already starts with country code 91 and is 12 digits, return as is
        if phone_str.startswith('91') and len(phone_str) == 12:
            return phone_str
        
        # Remove leading 0 if present (some Indian numbers have leading 0)
        if phone_str.startswith('0') and len(phone_str) == 11:
            phone_str = phone_str[1:]
        
        # Check if it's a 10-digit Indian number (starts with 6-9)
        if len(phone_str) == 10 and phone_str[0] in ['6', '7', '8', '9']:
            # Add country code 91 for Indian numbers
            return f"91{phone_str}"
        
        # If number already has country code (12+ digits starting with 91), return as is
        if phone_str.startswith('91') and len(phone_str) >= 12:
            return phone_str
        
        # If it's already 12+ digits (likely has country code), return as is
        if len(phone_str) >= 12:
            return phone_str
        
        # Default: assume it's an Indian number and add 91
        # Remove any leading zeros
        phone_str = phone_str.lstrip('0')
        if len(phone_str) == 10 and phone_str[0] in ['6', '7', '8', '9']:
            return f"91{phone_str}"
        
        # Return as is if we can't determine (fallback)
        return phone_str

    def get_otp(self,user,otp_type):
        user_otp=OTP.objects.filter(user=user,type=otp_type)
        if user_otp.exists():
            user_otp = user_otp.first()
            return user_otp.otp
        new_otp =self.generate_otp()
        OTP.objects.create(user=user,otp=new_otp,type=otp_type)
        return new_otp


    def send_mail(self,subject,to,text_content, html_content,attachment=None,attachment_name=None,attachment_type=None):
        status = False
        to_list = [to] if not isinstance(to, list) else to
        html_content = ensure_email_html_wrapped(html_content, preheader=subject)
        if not text_content or text_content == html_content:
            text_content = strip_tags(html_content) or html_content
        try:
            msg = EmailMultiAlternatives(subject, text_content, self.from_email, to_list)
            msg.attach_alternative(html_content, "text/html")
            if attachment and attachment_name and attachment_type:
                msg.attach(attachment_name, attachment, attachment_type)
            msg.send(fail_silently=False)
            status = True
            logger.info("Email sent to %s subject=%s", to_list, subject[:50] if subject else "")
        except Exception as e:
            logger.warning("Email sending failed to %s subject=%s: %s", to_list, subject[:50] if subject else "", e)
        # Convert to string if it's a list for logging purposes
        # log_to = to if isinstance(to, str) else ", ".join(to)
        self.make_log_entry(to, html_content, choices.CommunicationTypeChooices.EMAIL, status)
        return status

    def make_log_entry(self,to,body,com_type,response):
        from communication.utils import mysql_text_safe
        try:
            log_response = response if isinstance(response, str) else ('success' if response else 'failed')
            CommunicationLog.objects.create(
                to=mysql_text_safe(to) if isinstance(to, str) else to,
                body=mysql_text_safe(body),
                type=com_type,
                response=log_response,
            )
        except Exception as e:
            logger.warning("CommunicationLog create failed for %s: %s", to, e)


    def check_duplicate_sms(self,url):
        time_threshold =  datetime.now() - timedelta(seconds=30)
        return CommunicationLog.objects.filter(body=url,created__gte=time_threshold).exists()

    def build_email_subject(self,txt):
        return txt

    def send_email_otp(self,user):
        print()
        print(f"From Con_service",">"*30,user)
        print()
        otp = self.get_otp(user,choices.CommunicationTypeChooices.EMAIL)
        to=user
        subject, text_content, html_content = render_transactional_email(
            'email_otp',
            format_context={'otp': otp},
            django_context={'otp': otp},
        )
        print("Email otp",otp)
        if settings.DEBUG is False or True: #enabled for now
            return self.send_mail(subject,to,text_content,html_content)
        print("Email otp",otp)
        return True
    
    def send_pyschometric_payment_success_mail(self,user,test_payment):
        to=user
        candidate_test=test_payment.candidate_test.last()
        django_context = {"test_payment": test_payment, "candidate_test": candidate_test}
        test_link = getattr(candidate_test, 'test_link', '') if candidate_test else ''
        format_context = {'test_link': test_link}
        subject, text_content, html_content = render_transactional_email(
            'psychometric_payment_success',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_skillabcourse_payment_success_mail(self,user,course_payment):
        to=user
        django_context = {"course_payment": course_payment}
        course = getattr(course_payment, 'skilllab_course', None)
        course_name = getattr(course, 'name', '') if course else ''
        course_url = ''
        if course and getattr(course, 'slug', None):
            course_url = "https://topteen.in{}".format(
                reverse('skilllabcourse:skilllabcoursedetail', args=[course.slug])
            )
        format_context = {'course_name': course_name, 'course_url': course_url}
        subject, text_content, html_content = render_transactional_email(
            'skilllab_payment_success',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)

    def _should_send_mobile_message(self, log_key):
        """Respect DEBUG + force-send flags and 30s duplicate guard."""
        provider = getattr(settings, 'SMS_PROVIDER', 'smartping')
        if provider == 'plivo':
            force_send = getattr(settings, 'PLIVO_FORCE_SEND', False)
        else:
            force_send = getattr(settings, 'SMARTPING_SMS_FORCE_SEND', False)
        return (not settings.DEBUG or force_send) and (not self.check_duplicate_sms(log_key))

    def _send_mobile_otp_smartping(self, user, otp, formatted_phone):
        message_template = getattr(
            settings,
            'SMARTPING_SMS_MESSAGE_TEMPLATE',
            '{otp} is your verification code for TestprepGPT AI',
        )
        message = message_template.format(otp=otp)
        params = {
            'username': getattr(settings, 'SMARTPING_SMS_USERNAME', 'Testprepgpt.trans'),
            'password': getattr(settings, 'SMARTPING_SMS_PASSWORD', 'sW2gV'),
            'unicode': getattr(settings, 'SMARTPING_SMS_UNICODE', 'false'),
            'from': getattr(settings, 'SMARTPING_SMS_FROM', 'TSTGPT'),
            'to': formatted_phone,
            'dltContentId': getattr(settings, 'SMARTPING_SMS_DLT_CONTENT_ID', '1707175152949044040'),
            'dltPrincipalEntityId': getattr(settings, 'SMARTPING_SMS_DLT_PRINCIPAL_ENTITY_ID', '1701172845816093698'),
            'text': message,
        }
        api_url = getattr(settings, 'SMARTPING_SMS_API_URL', 'https://pgapi.smartping.ai/fe/api/v1/send')
        url = f"{api_url}?{urlencode(params)}"
        response_text = 'DEBUG'
        response_status = False

        if self._should_send_mobile_message(url):
            try:
                response = requests.get(url, timeout=10)
                if hasattr(response, 'content') and response.content:
                    try:
                        response_text = response.content.decode('utf-8')
                    except (UnicodeDecodeError, AttributeError):
                        response_text = str(response.content)
                else:
                    response_text = f"Status: {response.status_code}" if hasattr(response, 'status_code') else 'No content'
                response_status = getattr(response, 'status_code', None) == 200
                print(f"SmartPing SMS API Response: {response_text} (Status: {getattr(response, 'status_code', None)})")
            except requests.exceptions.RequestException as e:
                print(f"Error sending SMS via SmartPing API: {str(e)}")
                response_text = f"Error: {str(e)}"
                response_status = False
            except Exception as e:
                print(f"Unexpected error sending SMS via SmartPing API: {str(e)}")
                import traceback
                traceback.print_exc()
                response_text = f"Unexpected Error: {str(e)}"
                response_status = False
        else:
            print(f"DEBUG mode or duplicate SMS detected. URL: {url}")
            response_status = True

        self.make_log_entry(user, url, choices.CommunicationTypeChooices.SMS, response_text)
        return response_status

    def _send_mobile_otp_plivo(self, user, otp, formatted_phone):
        from communication.providers import plivo as plivo_provider

        message_template = getattr(
            settings,
            'PLIVO_SMS_MESSAGE_TEMPLATE',
            '{otp} is your verification code for TopTeen',
        )
        message = message_template.format(otp=otp)
        log_key = f"plivo:sms:{formatted_phone}:{message}"
        response_text = 'DEBUG'
        response_status = False

        if self._should_send_mobile_message(log_key):
            result = plivo_provider.send_sms(formatted_phone, message)
            response_text = result.get('response') or result.get('error') or ''
            response_status = bool(result.get('success'))
            print(f"Plivo SMS API Response: {response_text} (success={response_status})")
        else:
            print(f"DEBUG mode or duplicate Plivo SMS detected. key: {log_key}")
            response_status = True

        self.make_log_entry(user, log_key, choices.CommunicationTypeChooices.SMS, response_text)
        return response_status

    def send_mobile_otp(self, user):
        try:
            user = int(user)
            otp = self.get_otp(user, choices.CommunicationTypeChooices.SMS)
            print("sending mobile otp for {} is {}".format(user, otp))

            formatted_phone = self.format_phone_number_with_country_code(user)
            print(f"Formatted phone number: {formatted_phone} (original: {user})")

            provider = getattr(settings, 'SMS_PROVIDER', 'smartping')
            if provider == 'plivo':
                return self._send_mobile_otp_plivo(user, otp, formatted_phone)
            return self._send_mobile_otp_smartping(user, otp, formatted_phone)

        except Exception as e:
            print(f"Invalid mobile_number {user}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def send_whatsapp_otp(self, user, otp_type=None):
        """
        Send OTP via Plivo WhatsApp template (requires approved template + WABA number).

        otp_type controls which OTP record is stored/verified. When mobile OTP is routed
        through WhatsApp via OTP_MOBILE_CHANNEL=whatsapp, pass SMS so verify_otp still works.
        """
        from communication.providers import plivo as plivo_provider

        if not getattr(settings, 'WHATSAPP_ENABLED', False):
            logger.warning('WhatsApp OTP skipped: WHATSAPP_ENABLED is False')
            return False

        if otp_type is None:
            otp_type = choices.CommunicationTypeChooices.WHATSAPP

        try:
            user = int(user)
            otp = self.get_otp(user, otp_type)
            formatted_phone = self.format_phone_number_with_country_code(user)
            log_key = f"plivo:whatsapp-otp:{formatted_phone}:{otp}"
            response_text = 'DEBUG'
            response_status = False

            force_send = getattr(settings, 'PLIVO_FORCE_SEND', False)
            should_send = (not settings.DEBUG or force_send) and (not self.check_duplicate_sms(log_key))
            if should_send:
                result = plivo_provider.send_whatsapp_template(
                    formatted_phone,
                    body_params=[str(otp)],
                )
                response_text = result.get('response') or result.get('error') or ''
                response_status = bool(result.get('success'))
                print(f"Plivo WhatsApp OTP Response: {response_text} (success={response_status})")
            else:
                print(f"DEBUG mode or duplicate WhatsApp OTP detected. key: {log_key}")
                response_status = True

            self.make_log_entry(user, log_key, choices.CommunicationTypeChooices.WHATSAPP, response_text)
            return response_status
        except Exception as e:
            logger.exception('WhatsApp OTP failed for %s: %s', user, e)
            return False

    def send_whatsapp_message(self, to_number, text=None, *, template_name=None, body_params=None):
        """
        Send a WhatsApp message via Plivo.
        Pass template_name and/or body_params for an approved template;
        otherwise pass text for free-form (only inside an open session window).
        """
        from communication.providers import plivo as plivo_provider

        if not getattr(settings, 'WHATSAPP_ENABLED', False):
            logger.warning('WhatsApp message skipped: WHATSAPP_ENABLED is False')
            return False

        formatted_phone = self.format_phone_number_with_country_code(to_number)
        if template_name is not None or body_params is not None:
            result = plivo_provider.send_whatsapp_template(
                formatted_phone,
                template_name=template_name,
                body_params=body_params,
            )
        elif text:
            result = plivo_provider.send_whatsapp_text(formatted_phone, text)
        else:
            logger.warning('WhatsApp send requires text or template_name/body_params')
            return False

        response_text = result.get('response') or result.get('error') or ''
        self.make_log_entry(
            to_number,
            response_text or text or template_name or 'whatsapp',
            choices.CommunicationTypeChooices.WHATSAPP,
            response_text,
        )
        return bool(result.get('success'))

    def send_otp(self, user, otp_type):
        if otp_type == choices.CommunicationTypeChooices.EMAIL:
            return self.send_email_otp(user)
        if otp_type == choices.CommunicationTypeChooices.WHATSAPP:
            return self.send_whatsapp_otp(user)
        if otp_type == choices.CommunicationTypeChooices.SMS:
            # Optional: deliver SMS-typed OTP over WhatsApp (verify still uses SMS type)
            if (
                getattr(settings, 'OTP_MOBILE_CHANNEL', 'sms') == 'whatsapp'
                and getattr(settings, 'WHATSAPP_ENABLED', False)
            ):
                return self.send_whatsapp_otp(user, otp_type=choices.CommunicationTypeChooices.SMS)
            return self.send_mobile_otp(user)
        return None
        
    def verify_otp(self,user,otp,otp_type,delete=True):
        user_otp=OTP.objects.filter(user=user,otp=otp,type=otp_type)
        if user_otp.exists():
            if delete:
                user_otp.delete()
            return True
        return False
    
    def send_referral(self,user_id,to):
        from communication.email_templates import format_referral_email
        user=User.objects.get(id=user_id)
        url=user.get_referral_url()
        subject, text_content, html_content = format_referral_email(
            user=user,
            referral_url=url,
            invitee_email=to,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_student_create_mail(self,email,password,ins_name,image_url,test_link):
        to=email
        ins_logo_url="{}{}".format("https://www.topteen.in",image_url)
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        psychometric_test_url=test_link
        django_context = {
            "url": url,
            "email": email,
            "password": password,
            "ins_logo_url": ins_logo_url,
            "ins_name": ins_name,
            "psychometric_test_url": psychometric_test_url,
        }
        format_context = {
            **django_context,
            'url_no_scheme': referral_url_without_scheme(url),
        }
        subject, text_content, html_content = render_transactional_email(
            'student_invite',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_create_mail(self,email,password):
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        django_context = {"url": url, "email": email, "password": password}
        format_context = {**django_context, 'url_no_scheme': referral_url_without_scheme(url)}
        subject, text_content, html_content = render_transactional_email(
            'institute_invite',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    # Manish
    def send_institute_create_homepage_mail(self, email, password, Ins_name, principal_name, contact_number, Address, institute_type):
        to = email
        url = "{}{}".format("https://demo.topteen.in", reverse("users:login"))
        django_context = {
            "url": url,
            "email": email,
            "password": password,
            "Ins_name": Ins_name,
            "principal_name": principal_name,
            "contact_number": contact_number,
            "Address": Address,
            "institute_type": institute_type,
        }
        format_context = {
            **django_context,
            'ins_name': Ins_name,
            'address': Address,
            'url_no_scheme': referral_url_without_scheme(url),
        }
        subject, text_content, html_content = render_transactional_email(
            'institute_homepage_welcome',
            format_context=format_context,
            django_context=django_context,
        )
        status = self.send_mail(subject, to, text_content, html_content)
        return "Email sent to {}".format(email) if status else "Failed to send email to {}".format(email)
    
    def send_institute_create_homepage_mail_bulk(self, user_email, emails, password, Ins_name, principal_name, contact_number, Address, institute_type):
        """
        Send institute creation emails to multiple recipients
        emails: list of email addresses
        """
        results = []
        url = "{}{}".format("https://demo.topteen.in", reverse("users:login"))
        
        for email in emails:
            try:
                django_context = {
                    "url": url,
                    "user_email": user_email,
                    "email": email,
                    "password": password,
                    "Ins_name": Ins_name,
                    "principal_name": principal_name,
                    "contact_number": contact_number,
                    "Address": Address,
                    "institute_type": institute_type,
                }
                format_context = {
                    **django_context,
                    'ins_name': Ins_name,
                    'address': Address,
                    'url_no_scheme': referral_url_without_scheme(url),
                }
                subject, text_content, html_content = render_transactional_email(
                    'institute_marketing_notify',
                    format_context=format_context,
                    django_context=django_context,
                )
                status = self.send_mail(subject, email, text_content, html_content)
                results.append({"email": email, "status": "success", "result": status})
            except Exception as e:
                print(f"Error sending email to {email}: {str(e)}")
                results.append({"email": email, "status": "error", "error": str(e)})
        
        return results
    
    def test_email(self):
        try:
            res = self.send_mail(
                'Test Subject',
                'Test Message',
                'support@topteen.careers',
                ['support4.it@canamgroup.com'],
                fail_silently=False,
            )
            print("Test email sent successfully")
        except Exception as e:
            print(f"Error sending test email: {str(e)}")
    





    # Manish
    def send_counselor_create_mail(self,email,password):
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        django_context = {"url": url, "email": email, "password": password}
        format_context = {**django_context, 'url_no_scheme': referral_url_without_scheme(url)}
        subject, text_content, html_content = render_transactional_email(
            'counselor_invite',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_group_create_mail(self,group_name,email,password):
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        django_context = {"url": url, "email": email, "password": password, "group_name": group_name}
        format_context = {**django_context, 'url_no_scheme': referral_url_without_scheme(url)}
        subject, text_content, html_content = render_transactional_email(
            'institute_group_invite',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_student_change_password(self,email,password):
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        django_context = {"url": url, "email": email, "password": password}
        format_context = {**django_context, 'url_no_scheme': referral_url_without_scheme(url)}
        subject, text_content, html_content = render_transactional_email(
            'student_password_notify',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)


    def send_registration_success_mail(self,user):
        to=user.email
        format_context = {
            'name': user.name,
            'did': user.did,
            'email': user.email,
            'mobile': user.mobile,
        }
        django_context = format_context.copy()
        subject, text_content, html_content = render_transactional_email(
            'registration_success',
            format_context=format_context,
            django_context=django_context,
            default_subject=email_strings.EMAIL_REGISTRATION_SUCCESS.format(user.did),
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_deletion_request(self,ins_id,ins_name,reason):
        to=self.from_email
        format_context = {
            'institute_id': ins_id,
            'institute_name': ins_name,
            'reason': reason,
        }
        django_context = format_context.copy()
        subject, text_content, html_content = render_transactional_email(
            'institute_deletion_request',
            format_context=format_context,
            django_context=django_context,
        )
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_resume_builder_resume_mail(self,user,attachment=None,attachment_name=None,attachment_type=None):
        to=user.email
        subject, text_content, html_content = render_transactional_email(
            'resume_builder',
            django_context={},
        )
        return self.send_mail(subject,to,text_content,html_content,attachment,attachment_name,attachment_type)

    def send_registration_success_sms(self,user):
        import http.client
        import json
        conn = http.client.HTTPSConnection("api.msg91.com")
        payload = {
            "flow_id" : "5f060124d6fc054cba7ea103",
            "name" : user.name,
            "mobile" : user.mobile,
            "email":user.email,
            "did":user.did
            }

        headers = {
            'authkey': settings.MSG91_KEY,
            'content-type': "application/json"
            }
        conn.request("POST", "/api/v5/flow/", json.dumps(payload), headers)
        res = conn.getresponse()
        data = res.read()

        response = data.decode("utf-8")

        self.make_log_entry(user,payload,choices.CommunicationTypeChooices.SMS,response)
        
    def send_test_popup_answers_email(self, user, answers_data):
        """Send email to admins with test completion popup answers"""
        try:
            # Get admin emails from settings
            admin_emails = []
            if hasattr(settings, 'ADMINS') and settings.ADMINS:
                admin_emails = [email for _, email in settings.ADMINS]
            if hasattr(settings, 'EXCEPTION_EMAIL_TO') and settings.EXCEPTION_EMAIL_TO:
                admin_emails.extend(settings.EXCEPTION_EMAIL_TO)
            
            # Remove duplicates
            admin_emails = list(set(admin_emails))
            
            if not admin_emails:
                print("No admin emails configured for test popup answers notification")
                return False
            
            user_name = user.username or user.email
            django_context = {
                'user': user,
                'answers_data': answers_data,
                'personality_answer': answers_data.get('personality', {}).get('answer', 'Not answered'),
                'motivation_answer': answers_data.get('motivation', {}).get('answer', 'Not answered'),
                'career_answer': answers_data.get('career_interest', {}).get('answer', 'Not answered'),
                'career_country': answers_data.get('career_interest', {}).get('country', ''),
            }
            format_context = {
                **django_context,
                'user_email': user.email,
                'user_name': user.name or '',
                'user_username': user.username or '',
            }
            subject, text_content, html_content = render_transactional_email(
                'test_popup_answers',
                format_context=format_context,
                django_context=django_context,
                default_subject=f"Test Completion Popup Answers - {user_name}",
            )
            
            # Send to all admin emails
            return self.send_mail(subject, admin_emails, text_content, html_content)
        except Exception as e:
            print(f"Error sending test popup answers email: {str(e)}")
            return False
        
    

