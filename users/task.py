from topteens.celery import app
from communication.com_service import ComService
from io import BytesIO
from django.template.loader import get_template
from .models import User
# from xhtml2pdf import pisa

@app.task()
def send_otp_mail(username,otp_type):
    print()
    print(f"From Task",">"*30,username)
    print()
    cs=ComService()
    cs.send_otp(username,otp_type)
    print("Otp mail send successfully") 

@app.task()
def send_referral_mail(user_id,to):
    cs=ComService()
    return cs.send_referral(user_id,to)

# @app.task()
# def send_resume_mail(user_id):
#     cs=ComService()
#     user=User.objects.get(id=user_id)
#     template = get_template("mail/user/userresumepdf.html")
#     html  = template.render({})
#     result = BytesIO()
#     pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
#     pdf = result.getvalue()
#     filename="Resume.pdf"
#     cs.send_resume_builder_resume_mail(user,pdf,filename,'application/pdf')