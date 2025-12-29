
from django.conf import settings
from django.utils.crypto import get_random_string
import requests
from urllib.parse import urlencode
from core import choices
from .models import OTP,CommunicationLog
from django.core.mail import EmailMultiAlternatives
from core import email_strings, sms_strings
from django.template.loader import render_to_string
# from edmissions.celery import app
from django.utils.safestring import mark_safe
from django.template.loader import get_template
from datetime import datetime,timedelta 
from users.models import User
from django.urls import reverse

class ComService:
    _SERVICE_URL = settings.MOBILE_SMS_SERVICE
    from_email = settings.TOPTEEN_FROM_EMAIL

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
        status=False

        print("Sending email to:", to)
        try:
            if not isinstance(to, list):
                to = [to]
            msg = EmailMultiAlternatives(subject, text_content, self.from_email, to)
            msg.attach_alternative(html_content, "text/html")
            if attachment and attachment_name and attachment_type:
                msg.attach(attachment_name,attachment,attachment_type)
            status=msg.send()
        except Exception as e:
            print("Email sending error:", str(e))
        # Convert to string if it's a list for logging purposes
        # log_to = to if isinstance(to, str) else ", ".join(to)
        self.make_log_entry(to, html_content, choices.CommunicationTypeChooices.EMAIL, status)
        return status

    def make_log_entry(self,to,body,com_type,response):
        CommunicationLog.objects.create(to=to,body=body,type=com_type,response=response)


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
        subject=self.build_email_subject(email_strings.EMAIL_OTP_SUBJECT)
        to=user
        html_content=render_to_string('mail/user/otp.html', { 'otp': otp })
        text_content=html_content
        print("Email otp",otp)
        if settings.DEBUG is False or True: #enabled for now
            return self.send_mail(subject,to,text_content,html_content)
        print("Email otp",otp)
        return True
    
    def send_pyschometric_payment_success_mail(self,user,test_payment):
        subject=self.build_email_subject(email_strings.EMAIL_PYSCHOMETRIC_TEST_PAYMENT_SUCCESS)
        to=user
        candidate_test=test_payment.candidate_test.last()
        html_content=render_to_string('mail/user/pyschometrictestpaymentsucess.html', {"test_payment":test_payment,"candidate_test":candidate_test})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_skillabcourse_payment_success_mail(self,user,course_payment):
        subject=self.build_email_subject(email_strings.EMAIL_SKILLABCOURSE_PAYMENT_SUCCESS)
        to=user
        html_content=render_to_string('mail/user/skilllabcoursepaymentsuccess.html', {"course_payment":course_payment})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)

    def send_mobile_otp(self,user):
        try:
            user = int(user)
            otp = self.get_otp(user, choices.CommunicationTypeChooices.SMS)
            print("sending mobile otp for {} is {}".format(user, otp))
            
            # Format phone number with country code (default 91 for Indian numbers)
            formatted_phone = self.format_phone_number_with_country_code(user)
            print(f"Formatted phone number: {formatted_phone} (original: {user})")
            
            # SmartPing SMS API implementation
            # Format message using template from settings
            message_template = getattr(settings, 'SMARTPING_SMS_MESSAGE_TEMPLATE', '{otp} is your verification code for TestprepGPT AI')
            message = message_template.format(otp=otp)
            
            # Prepare API parameters
            # formatted_phone already has country code without + sign
            params = {
                'username': getattr(settings, 'SMARTPING_SMS_USERNAME', 'Testprepgpt.trans'),
                'password': getattr(settings, 'SMARTPING_SMS_PASSWORD', 'sW2gV'),
                'unicode': getattr(settings, 'SMARTPING_SMS_UNICODE', 'false'),
                'from': getattr(settings, 'SMARTPING_SMS_FROM', 'TSTGPT'),
                'to': formatted_phone,
                'dltContentId': getattr(settings, 'SMARTPING_SMS_DLT_CONTENT_ID', '1707175152949044040'),
                'dltPrincipalEntityId': getattr(settings, 'SMARTPING_SMS_DLT_PRINCIPAL_ENTITY_ID', '1701172845816093698'),
                'text': message
            }
            
            # Build the API URL
            api_url = getattr(settings, 'SMARTPING_SMS_API_URL', 'https://pgapi.smartping.ai/fe/api/v1/send')
            url = f"{api_url}?{urlencode(params)}"
            
            # Send SMS
            response_text = "DEBUG"
            response_status = False
            
            if settings.DEBUG is False and self.check_duplicate_sms(url) is False:
                try:
                    response = requests.get(url, timeout=10)
                    # Safely extract response content
                    if hasattr(response, 'content') and response.content:
                        try:
                            response_text = response.content.decode('utf-8')
                        except (UnicodeDecodeError, AttributeError):
                            response_text = str(response.content)
                    else:
                        response_text = f"Status: {response.status_code}" if hasattr(response, 'status_code') else "No content"
                    
                    # Check response status
                    if hasattr(response, 'status_code'):
                        response_status = response.status_code == 200
                        print(f"SmartPing SMS API Response: {response_text} (Status: {response.status_code})")
                    else:
                        response_status = False
                        print(f"SmartPing SMS API Response: {response_text} (No status code)")
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
                response_status = True  # Return True in DEBUG mode
            
            # Log the communication
            self.make_log_entry(user, url, choices.CommunicationTypeChooices.SMS, response_text)
            return response_status
            
        except Exception as e:
            print(f"Invalid mobile_number {user}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def send_otp(self,user,otp_type):
        if otp_type == choices.CommunicationTypeChooices.EMAIL:
            return self.send_email_otp(user)
        elif otp_type == choices.CommunicationTypeChooices.SMS:
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
        user=User.objects.get(id=user_id)
        subject="{} has invited you to explore careers in TopTeen".format(user)
        to=to
        url=user.get_referral_url()
        html_content=render_to_string('mail/user/referral.html',{"refral_url":url,"user":user})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_student_create_mail(self,email,password,ins_name,image_url,test_link):
        subject="You have been invited to join Topteen"
        to=email
        ins_logo_url="{}{}".format("https://www.topteen.in",image_url)
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        # psychometric_test_url="{}{}".format("https://www.topteen.in",reverse("psychometrictests:psychometrictest"))
        # psychometric_test_url="{}{}".format("http://127.0.0.1:8000",reverse("app:test_buttons"))
        psychometric_test_url=test_link
        html_content=render_to_string('mail/user/create_student.html',{"url":url,"email":email,"password":password,"ins_logo_url":ins_logo_url,"ins_name":ins_name,"psychometric_test_url":psychometric_test_url})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_create_mail(self,email,password):
        subject="You have been invited to join Topteen"
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        html_content=render_to_string('mail/user/create_institute.html',{"url":url,"email":email,"password":password})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    # Manish
    def send_institute_create_homepage_mail(self, email, password, Ins_name, principal_name, contact_number, Address, institute_type):
        subject = "Welcome aboard! Your Institute is Now Part of the TOPTEEN Journey"
        to = email
        url = "{}{}".format("https://demo.topteen.in", reverse("users:login"))               
        
        # Create a context dictionary with exactly matching variable names
        context = {
            "url": url,
            "email": email,
            "password": password,
            "Ins_name": Ins_name,  # This should match the template variable
            "principal_name": principal_name,
            "contact_number": contact_number,
            "Address": Address,
            "institute_type": institute_type  # Now passing the name instead of number
        }
        
        html_content = render_to_string('mail/user/create_institute_mail_principal.html', context)
        text_content = html_content
        status = self.send_mail(subject, to, text_content, html_content)
        # Return a message instead of the ComService object itself
        return "Email sent to {}".format(email) if status else "Failed to send email to {}".format(email)
    
    def send_institute_create_homepage_mail_bulk(self, user_email, emails, password, Ins_name, principal_name, contact_number, Address, institute_type):
        """
        Send institute creation emails to multiple recipients
        emails: list of email addresses
        """
        results = []
        url = "{}{}".format("https://demo.topteen.in", reverse("users:login"))
        subject = f"New Institute Registered on TOPTEEN – {institute_type}, {Address}"
        
        for email in emails:
            try:
                context = {
                    "url": url,
                    "user_email": user_email,
                    "email": email,
                    "password": password,
                    "Ins_name": Ins_name,
                    "principal_name": principal_name,
                    "contact_number": contact_number,
                    "Address": Address,
                    "institute_type": institute_type
                }
                
                html_content = render_to_string('mail/user/create_institute_mail_to_marketing.html', context)
                text_content = html_content
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
        subject="You have been invited to join Topteen"
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        html_content=render_to_string('mail/user/create_counselor.html',{"url":url,"email":email,"password":password})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_group_create_mail(self,group_name,email,password):
        subject="You have been invited to join Topteen"
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        html_content=render_to_string('mail/user/create_institute_group.html',{"url":url,"email":email,"password":password,"group_name":group_name})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_student_change_password(self,email,password):
        subject="You have been invited to join Topteen"
        to=email
        url="{}{}".format("https://www.topteen.in",reverse("users:login"))
        html_content=render_to_string('mail/user/student_change_password.html',{"url":url,"email":email,"password":password})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)


    def send_registration_success_mail(self,user):
        subject=self.build_email_subject(email_strings.EMAIL_REGISTRATION_SUCCESS.format(user.did))
        to=user.email
        html_content=render_to_string('mail/user/registration_success.html', { 'name': user.name,'did':user.did, 'email':user.email,'mobile':user.mobile })
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_institute_deletion_request(self,ins_id,ins_name,reason):
        subject="Institute Deletion Request"
        to=self.from_email
        html_content=render_to_string('mail/user/institute_account_del.html',{"institute_id":ins_id,"institute_name":ins_name,"reason":reason})
        text_content=html_content
        return self.send_mail(subject,to,text_content,html_content)
    
    def send_resume_builder_resume_mail(self,user,attachment=None,attachment_name=None,attachment_type=None):
        subject=self.build_email_subject(email_strings.EMAIL_RESUME_BUILDER_RESUME)
        to=user.email
        html_content=render_to_string('mail/user/userresume.html', {})
        text_content=html_content
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
            
            subject = f"Test Completion Popup Answers - {user.username or user.email}"
            
            # Prepare context for email template
            context = {
                'user': user,
                'answers_data': answers_data,
                'personality_answer': answers_data.get('personality', {}).get('answer', 'Not answered'),
                'motivation_answer': answers_data.get('motivation', {}).get('answer', 'Not answered'),
                'career_answer': answers_data.get('career_interest', {}).get('answer', 'Not answered'),
                'career_country': answers_data.get('career_interest', {}).get('country', ''),
            }
            
            html_content = render_to_string('mail/admin/test_popup_answers.html', context)
            text_content = html_content
            
            # Send to all admin emails
            return self.send_mail(subject, admin_emails, text_content, html_content)
        except Exception as e:
            print(f"Error sending test popup answers email: {str(e)}")
            return False
        
    

