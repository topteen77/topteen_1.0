from topteens.celery import app
from .models import SkilllabCoursePayment
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile



@app.task()
def send_skillabcourse_payment_success_mail(course_id):
    course_payment=SkilllabCoursePayment.objects.get(id=course_id)
    course_payment.send_payment_mail()
    print("Skillabcourse payment mail send")


